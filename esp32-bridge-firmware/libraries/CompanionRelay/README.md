# CompanionRelay

Connect **your own** ESP32 sketch to a self-hosted Companion relay hub: the
board dials out, authenticates, and receives the same WebSocket frames the
first-party sketches use. `companion relay push` (or the MCP server, or the
fleet tools) can then send it an image.

This library is the **transport**, not an OTA implementation. It does not call
`Update`, ACK chunks, or verify an MD5; those are the sketch's responsibility.
`RelayDevice.ino` is the complete reference receiver. `examples/RelayBlink`
only demonstrates the link and is not a flashable OTA target.

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

void onRelayFrame(uint8_t *data, size_t n) { /* binary frame bytes */ }
void onRelayText(const String &text)       { /* full control frame */ }
void onRelayCommand(const char *kind)      { /* convenience: kind only */ }

void setup() {
  CompanionRelayConfig cfg;
  cfg.wifiSSID     = "your-ssid";
  cfg.wifiPassword = "your-pass";
  cfg.relayHost    = "ota.example.com";
  cfg.relayPort    = 443;
  cfg.relayTLS     = true;
  cfg.caCert       = "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n";
  cfg.deviceToken  = "<COMPANION_RELAY_DEVICES_TOKEN>";
  cfg.deviceId     = "";                // empty -> MAC-derived unique id
  cfg.onFrame      = onRelayFrame;      // required
  cfg.onText       = onRelayText;       // full frame; needed for push_start size/md5
  cfg.onCommand    = onRelayCommand;    // optional
  cfg.pushActive   = nullptr;           // set while your Update runs
  CompanionRelay.begin(cfg);
}

void loop() { CompanionRelay.loop(); }
```

On first boot the library generates a per-board secret, stores it in NVS and
prints it. Register that secret with the hub's operator — the hub refuses a push
to a board whose secret does not match, which is what stops one compromised
agent from flashing your whole fleet.

`cfg.caCert` is required when `relayTLS` is true. `begin()` refuses to dial
rather than falling back to an unverified TLS connection.

## Push firmware

```bash
export COMPANION_RELAY_AGENTS_TOKEN=...
export COMPANION_RELAY_DEVICE_SECRET=...      # the SECRET the board printed
companion relay push --hub wss://ota.example.com --device <device-id> ./firmware.bin
```

This is the same link the two first-party sketches (`RelayDevice`,
`esp32_bridge`) use — the library is that code, not a reimplementation. A
receiver must implement the ArduinoOTA data phase itself: parse `push_start`,
feed bytes to `Update`, send one bare decimal ACK per chunk, and send `OK` (or
`ERROR ...`) after `Update.end()`. Copy that state machine from `RelayDevice.ino`
rather than pointing `relay push` at a link-only sketch.

## What the callbacks receive

`onFrame` receives binary frame payloads. `onText` receives each complete TEXT
control frame, including `push_start`'s JSON body with `size` and `md5`.
`onCommand` is an optional convenience that receives only the parsed `kind`
(for example `push_start` or `push_done`); use `onText` when the body matters.
The library does not ACK or verify the image.
