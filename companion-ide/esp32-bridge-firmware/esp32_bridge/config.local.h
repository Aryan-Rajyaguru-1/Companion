/**
 * Companion IDE — ESP32 Bridge WiFi configuration (TRACKED TEMPLATE)
 * ==================================================================
 * This file IS committed to git, but only with PLACEHOLDER values, so
 * testers and users have a ready-to-edit file for OTA bring-up.
 *
 * Using your own network credentials:
 *   1. Edit the defines below (STA_SSID / STA_PASS for router mode,
 *      or AP_SSID / AP_PASS to rename the bridge's own hotspot).
 *   2. Keep git from ever committing your personal values:
 *
 *        git update-index --skip-worktree config.local.h
 *
 *      (run inside companion-ide/esp32-bridge-firmware/esp32_bridge/).
 *   3. To receive future template updates again:
 *
 *        git update-index --no-skip-worktree config.local.h
 *
 * With untouched placeholders the firmware behaves exactly like before:
 * AP mode on SSID "ESP32-OTA", password "flashme!", IP 192.168.4.1.
 */

#ifndef CONFIG_LOCAL_H
#define CONFIG_LOCAL_H

// true  → ESP32 hosts its own Access Point (no router needed)
// false → ESP32 joins your existing WiFi router (STA mode)
#define WIFI_AP_MODE    true

// Access Point credentials (used when WIFI_AP_MODE = true)
#define AP_SSID         "ESP32-OTA"
#define AP_PASS         "flashme!"

// Station credentials (used when WIFI_AP_MODE = false)
// ← EDIT THESE for router mode, and set WIFI_AP_MODE to false above
#define STA_SSID        "YOUR_WIFI_SSID"
#define STA_PASS        "YOUR_WIFI_PASSWORD"

#endif /* CONFIG_LOCAL_H */
