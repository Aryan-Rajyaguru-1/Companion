/**
 * Companion RelayDevice — remote-OTA relay configuration (example copy)
 * =====================================================================
 * Remote OTA is OPTIONAL. If you flash over USB or use LAN OTA
 * (`--ota-mode local`) you can ignore this file entirely — RelayDevice.ino
 * falls back to its own safe defaults.
 *
 * To use it:
 *   1. cp config.example.h config.local.h     (config.local.h is git-ignored)
 *   2. fill in your WiFi, your relay host and the hub's DEVICES token
 *   3. flash, open the serial monitor, and copy the board's one-time SECRET
 *
 * Server side: see deploy/README.md in the repository root.
 */

#ifndef CONFIG_LOCAL_H
#define CONFIG_LOCAL_H

// ── WiFi ───────────────────────────────────────────────────────────
// The board needs a network path to your relay hub.
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASS       "YOUR_WIFI_PASSWORD"

// ── Relay endpoint ─────────────────────────────────────────────────
// Bare host, no scheme — the firmware builds the URL itself:
//   ws://RELAY_HOST:RELAY_PORT/device?token=DEVICE_TOKEN      (RELAY_TLS false)
//   wss://RELAY_HOST:RELAY_PORT/device?token=DEVICE_TOKEN     (RELAY_TLS true)
//
//   LAN:       RELAY_HOST "192.168.1.50"      RELAY_PORT 8931   RELAY_TLS false
//   Internet:  RELAY_HOST "ota.example.com"   RELAY_PORT 443    RELAY_TLS true
#define RELAY_HOST      "YOUR_HUB_LAN_IP"
#define RELAY_PORT      8931
#define RELAY_TLS       false

// ── Identity ───────────────────────────────────────────────────────
// DEVICE_TOKEN must equal COMPANION_RELAY_DEVICES_TOKEN on the hub.
#define DEVICE_TOKEN    "YOUR_DEVICE_TOKEN"

// DEVICE_ID identifies the board to the hub. Leave it commented unless you
// need a fixed name: the firmware then derives a unique id from the MAC, so
// two boards built from this same file cannot collide (a collision means they
// would each try to evict the other — and since 02728f2 the hub only lets a
// re-registration supersede an online id when the SECRET matches, so a
// same-default pair simply refuses rather than flip-flops).
#define DEVICE_ID       "esp32-bridge-01"

// ── Recovery path (optional) ──────────────────────────────────────
// Firmware normally arrives over the relay, so a board whose HUB or tunnel is
// unreachable can only be fixed with a USB cable. Set this to 1 and the board
// also serves ArduinoOTA on the LAN, so it can be re-flashed over WiFi:
//
//   companion ota upload <board-ip> --ota-mode local
//
// The board's LAN address is shown by `companion relay devices` (it advertises
// it in device_hello), so you do not have to guess it.
//
// Default 0: ArduinoOTA has no per-device secret of its own, so this is one
// more unauthenticated service on your network. Turn it on for boards you can
// reach over USB, and leave it off for boards on untrusted networks.
// #define RELAY_LAN_OTA 1

#endif /* CONFIG_LOCAL_H */