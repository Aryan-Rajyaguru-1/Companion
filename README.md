# Companion IDE

Wireless Arduino-compatible IDE — flash any microcontroller over WiFi.
Powered by Companion CLI (MIT licensed, no GPL obligations).

## One-command setup

Get the code first (or `git pull` inside an existing clone):

```bash
git clone -b ide https://github.com/Aryan-Rajyaguru-1/Companion.git
cd Companion
```

Installs everything — downloads the prebuilt CLI binary for your OS/arch (or builds it from source if Go is installed), initializes config + board index, and installs IDE dependencies:

```bash
bash scripts/setup.sh          # macOS / Linux
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # Windows
```

## Quick Start

### 1. Get Companion CLI
The CLI source is not in this checkout — either let the setup script above
download it into `bin/`, or grab it manually from:
https://github.com/Aryan-Rajyaguru-1/Companion/releases/tag/v0.1.0-alpha

If you have the full workspace, you can also build it:
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
