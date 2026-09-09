/**
 * Companion IDE — ESP32 Bridge WiFi configuration
 * ================================================
 * Copy this file to `config.local.h` (same folder as esp32_bridge.ino) and
 * edit the values for your network. `config.local.h` is git-ignored, so your
 * personal credentials never get committed.
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

#endif /* CONFIG_LOCAL_H */