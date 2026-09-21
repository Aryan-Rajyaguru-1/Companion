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

// DEVICE_ID must be unique per board — the hub keys devices by it, and a
// re-registration supersedes any earlier socket with the same id.
#define DEVICE_ID       "esp32-bridge-01"

#endif /* CONFIG_LOCAL_H */