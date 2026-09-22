# Windows — getting Companion running (tester notes)

Companion's CLI is a single self-contained `.exe`; the IDE is an Electron app.
This page lists the walls Windows testers actually hit, in the order you'll hit
them, with the fix for each. Nothing here is a workaround for a bug in your
code — it's the platform.

---

## 1. Choose your path first

| Path | What you need | Good for |
|---|---|---|
| **A. Installer** (easiest) | nothing but the download | normal testing |
| **B. Prebuilt CLI + dev IDE** | Node.js 18+, npm | testing the IDE itself |
| **C. Build everything** | Go 1.18+, Node.js 18+, npm | contributing |

**Check what the release actually contains before you plan:**
<https://github.com/Aryan-Rajyaguru-1/Companion/releases/latest>

If there is no `Companion-IDE-*.exe` asset, path A isn't available for that tag
and you must use path B. (The `v0.1.0-alpha` release has the Windows **CLI** but
no Windows IDE installer.)

---

## 2. Path A — installer

1. Download `Companion-IDE-<version>.exe` (or `companion-windows-amd64.exe` for
   the CLI on its own).
2. **SmartScreen will warn you.** The builds are not code-signed yet, so Windows
   shows *"Windows protected your PC"*. Choose **More info → Run anyway**. If
   your organisation blocks unsigned executables, use path B.
3. Put `companion.exe` in the IDE's `bin\` folder — the IDE auto-detects it
   there, so you never touch `PATH`.

## 3. Path B — prebuilt CLI + dev IDE

```powershell
git clone https://github.com/Aryan-Rajyaguru-1/Companion.git
cd Companion
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

- `-ExecutionPolicy Bypass` is required because the script is unsigned.
- The script downloads the prebuilt CLI **and verifies its SHA-256** against the
  release's `SHA256SUMS.txt`. A mismatch means a truncated/corrupt download —
  re-run it.
- Node.js must be 18 or newer: <https://nodejs.org> (the LTS installer). If
  `node -v` fails in a new terminal after installing, reopen the terminal so
  `PATH` is picked up.

Run the IDE in dev mode:

```powershell
cd companion-ide
npm run dev
```

`npm install` pulls ~400 MB (Electron). On a slow link it can look stalled for
minutes — that is normal. Behind a corporate proxy, set
`npm config set proxy http://user:pass@host:port` first.

---

## 4. USB flashing: install the serial driver

No COM port appears ⇒ the USB-serial chip has no driver. Identify the chip and
install the matching driver:

| Chip on the board | Driver |
|---|---|
| CP2102 / CP2104 (many ESP32 devkits) | Silicon Labs **CP210x VCP** |
| CH340 / CH341 (cheap clones, many Nanos) | **CH341SER** |
| FTDI FT232 | **FTDI VCP** |
| ESP32-S3/C3 native USB | built into Windows 10+ (no driver) |

Check in **Device Manager → Ports (COM & LPT)**. A board with no driver shows up
under *Other devices* with a warning triangle.

- The port appears only while the board is plugged in.
- If flashing hangs at `Connecting...`, hold **BOOT** while it resets (some
  boards need this the first time).
- Only one program can hold a COM port: close the Arduino IDE, PuTTY, or a
  second serial monitor before flashing.

---

## 5. Wireless upload: the five things that actually break it

1. **The ESP32 bridge is 2.4 GHz only.** It cannot join or serve a 5 GHz
   network. If your router publishes one SSID for both bands, force the 2.4 GHz
   one (or use the bridge's own AP mode, `SSID=ESP32-OTA`,
   `password=flashme!`).
2. **Windows Firewall.** The bridge listens on TCP **3333**. A prompt appears on
   first run — allow it on **Private** networks. Public-network profiles block
   it by default.
3. **The laptop must be on the same network as the bridge.** In AP mode that
   means joining `ESP32-OTA`; your normal internet connection pauses while you
   are on it.
4. **Bridge IP.** AP mode is always `192.168.4.1`. In STA mode read the IP the
   bridge prints on its serial console and put it in Bridge Settings.
5. **Wiring.** Bridge `GPIO17→target RX`, `GPIO16→target TX`, `GND→GND`, plus the
   reset/boot lines. **Never feed 5 V into the ESP32** — classic 5 V AVR targets
   need a level shifter (see `esp32_bridge.ino`'s header comment).

Sanity check that the bridge is alive and reachable:

```powershell
.\companion.exe board list-ports      # USB boards
.\companion.exe fleet discover        # mDNS-scan the LAN for bridges
```

---

## 6. `esptool` / `avrdude` are separate tools

For ESP targets Companion shells out to **esptool**, and for AVR targets to
**avrdude** — neither ships with Windows:

```powershell
py -m pip install esptool          # use py if python3 is not on PATH
winget install avrdude             # or copy it from an Arduino IDE install
```

Python itself: <https://python.org> (tick **Add python.exe to PATH** in the
installer). Verify with `py --version`.

The errors Companion prints now tell you the right command for your OS instead
of assuming Linux.

---

## 7. Remote OTA (off-LAN) on Windows

`companion ota upload --ota-mode remote` needs a **relay hub** reachable over
`wss://`. The hub is a single Go binary and runs fine on Windows:

```powershell
$env:COMPANION_RELAY_DEVICES_TOKEN="<hex>"; $env:COMPANION_RELAY_AGENTS_TOKEN="<hex>"
.\companion.exe relay hub --listen :8931
```

**But the bundled setup helpers are Linux/systemd-only** —
`deploy/install-relay-hub.sh` and `deploy/setup-tunnel.sh` rely on `systemd`,
`journalctl`, and `openssl`. On Windows you have three options:

1. Leave the hub running in a PowerShell window (fine for a testing session; it
   stops when you close the window or reboot).
2. Run the hub on any always-on Linux box / NAS / VPS via `deploy/README.md`.
3. Run the scripts under **WSL2** if you have it.

The TLS endpoint in front of the hub (Cloudflare Tunnel, nginx, Caddy) is a
separate install on whichever machine hosts the hub.

---

## 8. Reporting a bug

Include:

```powershell
.\companion.exe version
[System.Environment]::OSVersion.VersionString
```

…plus your board, whether USB or wireless, WiFi band (2.4/5 GHz), and the exact
command you ran. If a flash failed, the full output matters — the last 10 lines
usually contain the real cause (`no sync`, `Connecting...`, `Access is denied`).

