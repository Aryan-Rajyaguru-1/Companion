/**
 * Companion IDE — ESP32 Bridge WiFi configuration (tracked template)
 * ==================================================================
 * This file is committed with PLACEHOLDER values so testers have a
 * ready-to-edit file. It is safe to commit only while these values are
 * placeholders.
 *
 *   1. Edit AP_SSID / AP_PASS (or STA_SSID / STA_PASS), and OTA_PASSWORD.
 *   2. Keep personal values out of git:
 *
 *        git update-index --skip-worktree config.local.h
 *
 *      (run inside esp32-bridge-firmware/esp32_bridge/.)
 *   3. To receive future template updates again:
 *
 *        git update-index --no-skip-worktree config.local.h
 *
 * The firmware fails closed: an unchanged CHANGE_ME placeholder (or any
 * password shorter than 8 characters) refuses to start the Access Point,
 * and an unchanged OTA_PASSWORD disables LAN OTA. There is no public
 * default password.
 */

#ifndef CONFIG_LOCAL_H
#define CONFIG_LOCAL_H

// true  → ESP32 hosts its own Access Point (no router needed)
// false → ESP32 joins your existing WiFi router (STA mode)
#define WIFI_AP_MODE    true

// Access Point credentials (used when WIFI_AP_MODE = true).
// AP_PASS MUST be unique and at least 8 characters.
#define AP_SSID         "Companion-Bridge"
#define AP_PASS         "CHANGE_ME_AP_PASSWORD"

// Station credentials (used when WIFI_AP_MODE = false)
#define STA_SSID        "YOUR_WIFI_SSID"
#define STA_PASS        "YOUR_WIFI_PASSWORD"

// LAN OTA password. MUST be unique and at least 8 characters to enable
// ArduinoOTA recovery. An unchanged placeholder disables LAN OTA; remote
// OTA through the relay is unaffected.
#define OTA_PASSWORD    "CHANGE_ME_OTA_PASSWORD"

// ── Remote relay (optional) ──────────────────────────────────────
// Default (0): LAN TCP server on TCP_PORT — the normal local workflow.
// Set to 1 to dial a self-hosted relay hub instead:
//   companion relay bridge --hub wss://<your-host> --device <DEVICE_ID>
// #define RELAY_MODE_REMOTE 1
// #define RELAY_HOST        "ota.example.com"
// #define RELAY_PORT        443
// #define RELAY_TLS         true
// REQUIRED for wss://: PEM trust anchor for the hub certificate.
// #define RELAY_CA_CERT     "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"
// Optional fixed device id. Leave commented to derive companion-bridge-<MAC>.
// #define DEVICE_ID         "companion-bridge-01"
// #define DEVICE_TOKEN      "..."   // COMPANION_RELAY_DEVICES_TOKEN from relay.env

#endif /* CONFIG_LOCAL_H */
