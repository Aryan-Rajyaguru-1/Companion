# CompanionRelay

Add internet firmware updates to **your own** ESP32 sketch: the board dials a
self-hosted Companion relay hub outbound, and `companion relay push` (or the MCP
server, or the fleet tools) flashes it from anywhere.

## Install

Copy `src/CompanionRelay.h` into your sketch folder, or add this folder to your
Arduino libraries directory.

## Use

```cpp
#include <CompanionRelay.h>

void onRelayFrame(uint8_t *data, size_t n) { /* the pushed image bytes */ }
void onRelayCommand(const char *kind)      { /* "start", "done" */ }

void setup() {
  CompanionRelayConfig cfg;
  cfg.wifiSSID     = "your-ssid";
  cfg.wifiPassword = "your-pass";
  cfg.relayHost    = "ota.example.com";
  cfg.relayPort    = 443;
  cfg.relayTLS     = true;
  cfg.deviceToken  = "<COMPANION_RELAY_DEVICES_TOKEN>";
  cfg.deviceId     = "esp32-node-01";   // unique per board
  cfg.onFrame      = onRelayFrame;      // required
  cfg.onCommand    = onRelayCommand;    // optional
  CompanionRelay.begin(cfg);
}

void loop() { CompanionRelay.loop(); }
```

On first boot the library generates a per-board secret, stores it in NVS and
prints it. Register that secret with the hub's operator — the hub refuses a push
to a board whose secret does not match, which is what stops one compromised
agent from flashing your whole fleet.

## Push firmware

```bash
export COMPANION_RELAY_AGENTS_TOKEN=...
export COMPANION_RELAY_DEVICE_SECRET=...      # the SECRET the board printed
companion relay push --hub wss://ota.example.com --device esp32-node-01 ./firmware.bin
```

This is the same link the two first-party sketches (`RelayDevice`,
`esp32_bridge`) use — the library is that code, not a reimplementation.

## What `onFrame` receives

The pushed image in the ArduinoOTA data-phase framing: a bare decimal ACK per
chunk is expected back through the library, and a bare `OK` when the board has
verified the MD5. See `examples/RelayBlink` for a complete one.
