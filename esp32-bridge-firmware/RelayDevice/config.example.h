/**
 * Companion RelayDevice — remote-OTA relay configuration (example copy)
 * =====================================================================
 * Remote OTA is OPTIONAL. You can ignore this file when you flash over USB,
 * but LAN OTA (`--ota-mode local`) still needs WIFI_SSID/WIFI_PASS so the board
 * is on the network. RelayDevice.ino otherwise uses fail-closed defaults and
 * will not dial a placeholder host or enable LAN OTA without a password.
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
//   ws://RELAY_HOST:RELAY_PORT/device      (RELAY_TLS false)
//   wss://RELAY_HOST:RELAY_PORT/device     (RELAY_TLS true)
// The role token travels in `Authorization: Bearer`, never in the URL.
//
//   LAN:       RELAY_HOST "192.168.1.50"      RELAY_PORT 8931   RELAY_TLS false
//   Internet:  RELAY_HOST "ota.example.com"   RELAY_PORT 443    RELAY_TLS true
#define RELAY_HOST      "YOUR_HUB_LAN_IP"
#define RELAY_PORT      8931
#define RELAY_TLS       false

// REQUIRED when RELAY_TLS is true: PEM trust anchor used to verify the hub
// certificate. The firmware refuses to dial an unverified wss:// hub.
// #define RELAY_CA_CERT "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"

// ── Identity ───────────────────────────────────────────────────────
// DEVICE_TOKEN must equal COMPANION_RELAY_DEVICES_TOKEN on the hub.
#define DEVICE_TOKEN    "YOUR_DEVICE_TOKEN"

// DEVICE_ID identifies the board to the hub. Leave it commented unless you
// need a fixed name: the firmware then derives a unique id from the MAC, so
// two boards built from this same file cannot collide (a collision means they
// would each try to evict the other — and since 02728f2 the hub only lets a
// re-registration supersede an online id when the SECRET matches, so a
// same-default pair simply refuses rather than flip-flops).
// #define DEVICE_ID       "lab-relay-a"   // must be unique per board

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
// more service on your network. Turn it on for boards you can reach over USB,
// and leave it off for boards on untrusted networks. When enabled, set
// RELAY_LAN_OTA_PASSWORD to at least 8 unique characters; otherwise the LAN
// OTA service stays disabled (fail closed).
// #define RELAY_LAN_OTA 1
// #define RELAY_LAN_OTA_PASSWORD "CHANGE_ME_LAN_OTA_PASSWORD"

#endif /* CONFIG_LOCAL_H */