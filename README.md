# Companion CLI

**An original Go CLI for the Companion IDE wireless Arduino programmer.**

Written entirely from scratch. Inspired by the arduino-cli architecture but
not derived from its source code — **MIT licensed, no GPL obligations.**

---

## Get the code

```bash
git clone -b cli https://github.com/Aryan-Rajyaguru-1/Companion.git
cd Companion
```

Already cloned? Run `git pull` to update.

## Quick Start

```bash
# One-command setup (recommended)
bash scripts/setup.sh          # macOS / Linux
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # Windows

Builds the CLI from source (Go) or downloads the prebuilt binary, then
initializes config and board indexes automatically.

# Manual build
go mod tidy
go build -o companion .

# First-time setup
./companion config init
./companion board update-index
./companion lib update-index

# Install board support
./companion board install arduino:avr        # Arduino Uno/Mega/Nano
./companion board install esp32:esp32        # ESP32 family

# Compile
./companion compile MySketch/ --fqbn arduino:avr:uno

# Upload wirelessly (compile + upload in one step)
./companion upload MySketch/ --fqbn arduino:avr:uno --mcu avr

# Serial monitor
./companion monitor --baud 115200
```

---

## Commands

| Command | Description |
|---|---|
| `compile [dir]` | Compile a sketch for a given FQBN |
| `upload [dir]` | Compile + upload wirelessly via bridge |
| `board update-index` | Download latest board package indexes |
| `board search [query]` | Search available boards |
| `board list` | List installed platforms |
| `board install <id>` | Install a board platform (e.g. `arduino:avr`) |
| `lib update-index` | Download the library index (9,359 libraries) |
| `lib search <query>` | Search libraries by name/category/author |
| `lib list` | List installed libraries |
| `lib install <name>` | Install a library |
| `lib uninstall <name>` | Remove a library |
| `monitor` | Interactive serial terminal via bridge |
| `config init` | Create default config file |
| `config get <key>` | Get a config value |
| `config set <key> <val>` | Set a config value |
| `config dump` | Print full config |
| `version` | Print version info |
| `version ping` | Ping the ESP32 bridge |

---

## Config File

Located at `~/.companion-cli/config.yaml`

```yaml
board_manager:
  additional_urls:
    - https://dl.espressif.com/dl/package_esp32_index.json
    - https://arduino.esp8266.com/stable/package_esp8266com_index.json
    - https://raw.githubusercontent.com/stm32duino/BoardManagerFiles/main/package_stmicroelectronics_index.json

directories:
  data: ~/.companion-cli/data
  user: ~/CompanionSketches

compiler:
  warnings: default    # none | default | more | all
  verbose: false

upload:
  auto_verify: true
  verbose: false

bridge:
  host: 192.168.4.1   # ESP32 AP mode default
  port: 3333
  baud: 115200
  mcu: avr            # esp32 | esp8266 | avr | stm32 | generic
```

---

## Supported MCU Families

| MCU | Upload method | Requirement |
|---|---|---|
| `esp32` / `esp8266` | esptool.py | `pip install esptool` |
| `avr` | avrdude | `sudo apt install avrdude` |
| `stm32` | Built-in AN3155 | None — native implementation |
| `generic` | Raw byte stream | None — custom bootloader |

---

## Architecture

```
companion-cli/
├── main.go
├── cmd/
│   ├── root.go       ← cobra root, global flags, color helpers
│   ├── compile.go    ← compile command
│   ├── upload.go     ← upload command (compile + wireless upload)
│   ├── board.go      ← board update-index / search / list / install
│   ├── lib.go        ← lib update-index / search / list / install
│   ├── monitor.go    ← serial monitor
│   ├── config.go     ← config init / get / set / dump
│   └── version.go    ← version + ping
└── internal/
    ├── config/       ← YAML config management
    ├── boards/       ← board index, platform install, FQBN resolution
    ├── compiler/     ← 10-stage build pipeline (GCC toolchain invocation)
    ├── libraries/    ← library index, search, install
    ├── uploader/     ← MCU-specific upload (ESP/STM32/AVR/Generic)
    └── bridge/       ← ESP32 TCP bridge client + control protocol
```

---

## License

MIT — fully owned by you. No GPL obligations.

The Companion CLI is an original work. It is **inspired** by the arduino-cli
architecture (studied as reference) but contains no copied source code.
