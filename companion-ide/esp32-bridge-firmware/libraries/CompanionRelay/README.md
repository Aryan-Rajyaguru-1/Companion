# CompanionRelay

Add internet firmware updates to **your own** ESP32 sketch: the board dials a
self-hosted Companion relay hub outbound, and `companion relay push` (or the MCP
server, or the fleet tools) flashes it from anywhere.

## Install

Copy this folder into your Arduino libraries directory:

```bash
cp -r libraries/CompanionRelay ~/Arduino/libraries/
```

**Keep exactly one copy.** If an older `CompanionRelay` is also sitting in
`~/Arduino/libraries/`, the Arduino build resolves `#include
<CompanionRelay.h>` by search order, not by date — so a stale copy quietly
wins and you compile a different protocol than the one you are reading. When
you pull changes from this repository, re-copy the folder (or `rsync -a
--delete`) rather than merging into the installed copy. The two first-party
sketches are immune, because they include the file by relative path.

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
