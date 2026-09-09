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
