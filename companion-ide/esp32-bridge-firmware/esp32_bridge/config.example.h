/**
 * Companion IDE — ESP32 Bridge WiFi configuration (example copy)
 * ================================================
 * NOTE: `config.local.h` is now shipped in the repo as a tracked TEMPLATE
 * with placeholder values — you can edit it directly. This example file is
 * kept as a reference for the shape of the configuration.
 *
 * After entering your personal credentials in config.local.h, run:
 *   git update-index --skip-worktree config.local.h
 * so your values are never committed.
 *
 * If `config.local.h` does not exist, the firmware falls back to the safe
 * defaults defined in esp32_bridge.ino (Access Point mode).
 */

#ifndef CONFIG_LOCAL_H
#define CONFIG_LOCAL_H

// true  → ESP32 hosts its own Access Point (no router needed)
// false → ESP32 joins your existing WiFi router (STA mode)
#define WIFI_AP_MODE    false

// Access Point credentials (used when WIFI_AP_MODE = true)
#define AP_SSID         "ESP32-OTA"
#define AP_PASS         "flashme!"

// Station credentials (used when WIFI_AP_MODE = false)
#define STA_SSID        "YOUR_WIFI_SSID"
#define STA_PASS        "YOUR_WIFI_PASSWORD"

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
// #define DEVICE_ID         "companion-bridge-01"  // unique per bridge
// #define DEVICE_TOKEN      "..."                  // COMPANION_RELAY_DEVICES_TOKEN from relay.env

#endif /* CONFIG_LOCAL_H */