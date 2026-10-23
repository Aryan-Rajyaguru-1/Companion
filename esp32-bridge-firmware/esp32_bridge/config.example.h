/**
 * Companion IDE — ESP32 Bridge WiFi configuration (example copy)
 * ================================================
 * `config.local.h` is git-ignored and is NOT tracked. Copy this example:
 *
 *   cp config.example.h config.local.h
 *
 * then fill in private credentials and flash. The firmware refuses an open
 * Access Point and disables LAN OTA when no real password is configured; it
 * never falls back to public defaults.
 */

#ifndef CONFIG_LOCAL_H
#define CONFIG_LOCAL_H

// true  → ESP32 hosts its own Access Point (no router needed)
// false → ESP32 joins your existing WiFi router (STA mode)
#define WIFI_AP_MODE    true

// Access Point credentials (used when WIFI_AP_MODE = true).
// AP_PASS MUST be unique and at least 8 characters; an empty/short/default
// value makes setup refuse to start the AP (fail closed).
#define AP_SSID         "Companion-Bridge"
#define AP_PASS         "CHANGE_ME_AP_PASSWORD"

// Station credentials (used when WIFI_AP_MODE = false)
#define STA_SSID        "YOUR_WIFI_SSID"
#define STA_PASS        "YOUR_WIFI_PASSWORD"

// LAN OTA password. MUST be unique and at least 8 characters to enable the
// ArduinoOTA recovery service. Empty/placeholder disables LAN OTA entirely;
// remote OTA through the relay is unaffected.
#define OTA_PASSWORD    "CHANGE_ME_OTA_PASSWORD"

// ── Remote relay (optional) ──────────────────────────────────────
// Default (0): the bridge hosts its usual TCP server on TCP_PORT and the IDE
// connects to it directly — the normal local workflow, unchanged.
//
// Set to 1 to make the bridge DIAL a self-hosted relay hub instead, so a
// target with no radio can be flashed from anywhere on the internet:
//   companion relay bridge --hub wss://<your-host> --device <DEVICE_ID>
// Hub setup + full walkthrough: deploy/README.md (section 6).
//
// #define RELAY_MODE_REMOTE 1
// #define RELAY_HOST        "ota.example.com"      // the hub's TLS endpoint
// #define RELAY_PORT        443
// #define RELAY_TLS         true                   // wss:// — required behind a proxy
// REQUIRED when RELAY_TLS is true: PEM trust anchor for the hub certificate.
// The sketch refuses to dial an unverified wss:// hub. For a public CA, paste
// the issuing root/intermediate certificate; for a private CA, paste that CA.
// #define RELAY_CA_CERT     "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"
// Device id on the hub. LEAVE THIS COMMENTED unless you really need a fixed
// name: the default id is "companion-bridge-<MAC>" (derived from the board, so
// two boards from this same config never collide — and colliding boards would
// take turns evicting each other from the hub). Setting it explicitly pins the
// id, which only makes sense for a single known board.
// #define DEVICE_ID         "companion-bridge-01"
// #define DEVICE_TOKEN      "..."                  // COMPANION_RELAY_DEVICES_TOKEN from relay.env

#endif /* CONFIG_LOCAL_H */