# Companion IDE

Wireless Arduino-compatible IDE — flash any microcontroller over WiFi.
Powered by Companion CLI (MIT licensed, no GPL obligations).

## Quick Start

### 1. Build Companion CLI first
```bash
cd companion-cli
go mod tidy && go build -o companion .
```

### 2. Initialize
```bash
./companion config init
./companion board update-index
./companion board install arduino:avr
```

### 3. Run IDE
```bash
cd companion-ide
npm install && npm run dev
```

## Updates

Open **Help → Check for Updates…**. The IDE runs the bundled CLI's
`self-update --check --json`, compares its own `app.getVersion()` with the
release tag, and shows both CLI and IDE status. From the panel you can:

- install a CLI update, which is written to `~/.companion-cli/bin/` and takes
  precedence over the bundled copy on the next launch;
- open the published IDE installer for this platform;
- open the release page.

The IDE never silently replaces its own installation. IDE updates open an
installer (a manual step) until signed installer/updater metadata is
configured. Releases may not contain an installer for every
platform/architecture; in that case the panel opens the release page instead.

## Architecture
- companion-cli.js  — wraps Companion CLI binary via spawn()
- bridge-client.js  — direct TCP to ESP32 bridge
- React UI: Editor, Toolbar, Console, SerialMonitor, BoardManager, Preferences, CLISetup

## MCU Support
| Family     | Method        | Requires           |
|------------|---------------|--------------------|
| ESP32/8266 | esptool.py    | pip install esptool|
| AVR        | avrdude       | apt install avrdude|
| STM32      | Built-in AN3155 | None             |
| Generic    | Raw bytes     | None               |

## License: MIT — fully owned by you, no GPL obligations.
