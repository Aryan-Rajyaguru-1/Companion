/**
 * Companion IDE — ESP32 WROOM Bridge Firmware
 * ============================================
 * Flash this onto your ESP32 WROOM bridge device.
 *
 * This sketch makes the ESP32 a wireless TCP↔UART bridge.
 * The Companion IDE on your laptop connects over WiFi,
 * sends control commands (enter bootloader, set baud, etc.)
 * and streams firmware bytes which are forwarded to the
 * target MCU over UART2.
 *
 * GitHub: https://github.com/arduino/arduino-cli  ← used by host IDE
 *
 * ── Quick wiring ──────────────────────────────────────────────
 *  ESP32 GPIO17 (TX2) → Target RX
 *  ESP32 GPIO16 (RX2) → Target TX
 *  ESP32 GPIO4        → Target EN / RST / NRST
 *  ESP32 GPIO5        → Target BOOT / GPIO0 / BOOT0
 *  ESP32 GND          → Target GND  ← REQUIRED
 *
 *  ── Logic-level note ──────────────────────────────────────────
 *  ESP32 is 3.3V only. Classic 5V AVR targets (e.g. Uno/Nano/Mega)
 *  need a bidirectional level-shifter on UART (TX/RX) and on the
 *  EN/RST + BOOT/GPIO0 control lines — do NOT connect 5V directly.
 *  STM32 targets are supported via the built-in UART bootloader only
 *  (BOOT0 + NRST sequencing); SWD programming is NOT supported.
 */

#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>

// ── WiFi configuration (overridable) ──────────────────────────
// config.local.h (this folder) is tracked as a sanitized TEMPLATE with
// placeholder values so testers can edit it directly. After putting in
// personal credentials, run:
//   git update-index --skip-worktree config.local.h
// so they are never committed. If the file is absent, the safe AP-mode
// defaults below are used.
#if __has_include("config.local.h")
  #include "config.local.h"
#endif

// ── Defaults (only used when config.local.h is not present) ────
// Set WIFI_AP_MODE to:
//   true  → ESP32 hosts its own Access Point (no router needed)
//           → IDE connects to "ESP32-OTA" WiFi network
//           → Then use IP: 192.168.4.1 in Bridge Settings
//   false → ESP32 joins your existing WiFi router (STA mode)
//           → IDE finds ESP32 on same network via MDNS or by IP
#ifndef WIFI_AP_MODE
  #define WIFI_AP_MODE    true
#endif

// AP mode credentials (used when WIFI_AP_MODE = true)
#ifndef AP_SSID
  #define AP_SSID         "ESP32-OTA"
#endif
#ifndef AP_PASS
  #define AP_PASS         "flashme!"
#endif

// STA mode credentials (used when WIFI_AP_MODE = false)
// To use STA mode, create config.local.h with your own SSID/PASS.
#ifndef STA_SSID
  #define STA_SSID        "YOUR_WIFI_SSID"
#endif
#ifndef STA_PASS
  #define STA_PASS        "YOUR_WIFI_PASSWORD"
#endif

// ── Wireless OTA server mode (Phase 4c) ───────────────────────
// The bridge itself can be re-flashed over WiFi via ArduinoOTA, so a
// misconfigured firmware never bricks the device. Point `companion ota
// upload <ip>` at the bridge's IP to push a new bridge build.
#ifndef OTA_HOSTNAME
  #define OTA_HOSTNAME    "companion-bridge"
#endif
#ifndef OTA_HOSTNAME_DEFAULT
  #define OTA_HOSTNAME_DEFAULT "companion-bridge"
#endif
#ifndef OTA_PASSWORD
  #define OTA_PASSWORD    ""   // set in config.local.h to require auth
#endif
// Resolved at runtime in setup(): stays OTA_HOSTNAME when the user
// overrode it in config.local.h, otherwise becomes companion-XXXXXX
// built from the last 3 bytes of WiFi.macAddress() so multiple
// bridges on one LAN get unique OTA/mDNS hostnames.
char otaHostname[32] = OTA_HOSTNAME_DEFAULT;
void resolveOtaHostname() {
  if (strcmp(OTA_HOSTNAME, OTA_HOSTNAME_DEFAULT) != 0) {
    strncpy(otaHostname, OTA_HOSTNAME, sizeof(otaHostname) - 1);
    otaHostname[sizeof(otaHostname) - 1] = '\0';
    return;
  }
  String mac = WiFi.macAddress(); // "AA:BB:CC:DD:EE:FF"
  // Last 3 bytes = chars at 9,10,12,13,15,16 (skip colons).
  char suffix[7];
  int n = 0;
  const int pick[6] = { 9, 10, 12, 13, 15, 16 };
  for (int i = 0; i < 6 && n < 6; i++) {
    int idx = pick[i];
    char c = (idx < (int)mac.length()) ? mac.charAt(idx) : '0';
    if (c == ':') c = '0';
    // Normalise to uppercase hex.
    if (c >= 'a' && c <= 'f') c = (char)(c - 'a' + 'A');
    suffix[n++] = c;
  }
  suffix[n] = '\0';
  snprintf(otaHostname, sizeof(otaHostname), "companion-%s", suffix);
}

// ── TCP server ────────────────────────────────────────────────
#define TCP_PORT        3333

// ── UART to target ────────────────────────────────────────────
#define UART_RX_PIN     16
#define UART_TX_PIN     17

// ── Target control pins ───────────────────────────────────────
#define PIN_TARGET_EN   4   // Active LOW reset: connect to EN / RST / NRST
#define PIN_TARGET_BOOT 5   // Bootloader entry: connect to GPIO0 / BOOT0

// ── Buffer ────────────────────────────────────────────────────
#define BUF_SIZE        2048

// ── Firmware version ─────────────────────────────────────────
#define FW_VERSION      "OTA-BRIDGE v1.1"

// ── Control protocol (matches bridge-client.js) ───────────────
#define CTRL_A              0xEF
#define CTRL_B              0xBE
#define CMD_ENTER_BOOT      0x01
#define CMD_RESET           0x02
#define CMD_RELEASE         0x03
#define CMD_SET_BAUD        0x10   // + 4 bytes uint32 big-endian
#define CMD_SET_PROFILE     0x11   // + 1 byte profile index
#define CMD_QUERY           0x20

// ── MCU Reset Profiles ────────────────────────────────────────
struct MCUProfile {
  const char* name;
  bool        bootPinActiveHigh; // true = STM32 (BOOT0 HIGH), false = ESP (GPIO0 LOW)
  uint16_t    resetHoldMs;
};

const MCUProfile profiles[] = {
  /* 0 */ { "Generic",   false, 100 },
  /* 1 */ { "ESP32",     false, 100 },
  /* 2 */ { "AVR",       false,  60 },
  /* 3 */ { "STM32",     true,  100 },
};

// ── State ─────────────────────────────────────────────────────
uint8_t  currentProfile = 0;
uint32_t currentBaud    = 115200;

WiFiServer tcpServer(TCP_PORT);
WiFiClient tcpClient;
uint8_t    buf[BUF_SIZE];

// ── Control-frame parser state (persistent across loop() reads) ──
// Frame format: CTRL_A CTRL_B <cmd byte + args>. The magic pair is
// only special at a frame boundary (parser idle); inside the payload
// or between split reads, raw 0xEF 0xBE bytes pass through untouched.
// Incomplete reads are buffered here until the full command arrives.
#define CTRL_FRAME_MAX  8   // longest command: magic(2)+SET_BAUD(1+4)
uint8_t  ctrlBuf[CTRL_FRAME_MAX];
uint8_t  ctrlLen = 0;       // bytes buffered in ctrlBuf (0 = idle)

// Forward declarations (Arduino generates prototypes, but be explicit).
int handleControl(uint8_t* payload, int available);
void pumpTcpByte(uint8_t b);
int ctrlFrameLength(uint8_t cmd);

// Total payload bytes (cmd byte + args) a command needs.
// Returns 0 only if cmd byte not yet known (never called that way).
int ctrlFrameLength(uint8_t cmd) {
  switch (cmd) {
    case CMD_SET_BAUD:    return 5; // cmd + 4-byte big-endian baud
    case CMD_SET_PROFILE: return 2; // cmd + 1-byte index
    case CMD_ENTER_BOOT:
    case CMD_RESET:
    case CMD_RELEASE:
    case CMD_QUERY:
    default:              return 1; // single-byte commands; unknown too
  }
}

// Feed one TCP byte through the frame parser.
void pumpTcpByte(uint8_t b) {
  if (ctrlLen == 0) {
    // Frame boundary: only here is CTRL_A potentially magic.
    if (b == CTRL_A) { ctrlBuf[0] = b; ctrlLen = 1; return; }
    Serial2.write(b);
    return;
  }
  if (ctrlLen == 1) {
    // Held a lone CTRL_A; this byte decides.
    if (b == CTRL_B) { ctrlBuf[1] = b; ctrlLen = 2; return; }
    Serial2.write(CTRL_A); // false alarm — flush held byte
    if (b == CTRL_A) { ctrlBuf[0] = b; ctrlLen = 1; } // re-hold, stay armed
    else { ctrlLen = 0; Serial2.write(b); }
    return;
  }
  // Inside a frame: accumulate (never scan for magic here).
  if (ctrlLen >= CTRL_FRAME_MAX) {
    // Should be unreachable (longest frame is 7 bytes); fail safe by
    // flushing buffered bytes raw and restarting from this byte.
    Serial2.write(ctrlBuf, ctrlLen);
    ctrlLen = 0;
    pumpTcpByte(b);
    return;
  }
  ctrlBuf[ctrlLen++] = b;
  int need = ctrlFrameLength(ctrlBuf[2]);
  if ((int)(ctrlLen - 2) >= need) {
    handleControl(ctrlBuf + 2, ctrlLen - 2);
    ctrlLen = 0;
  }
  // Else: split command — wait for more bytes across future reads.
}

// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n" FW_VERSION);

  // Init target control pins — idle state
  pinMode(PIN_TARGET_EN,   OUTPUT);
  pinMode(PIN_TARGET_BOOT, OUTPUT);
  pinsRelease();

  // Init UART to target
  Serial2.begin(currentBaud, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);

  // WiFi
#if WIFI_AP_MODE
  WiFi.softAP(AP_SSID, AP_PASS);
  Serial.println("\n╔════════════════════════════════════════════════════╗");
  Serial.println("║         ESP32 ACCESS POINT MODE (AP)              ║");
  Serial.println("╚════════════════════════════════════════════════════╝");
  Serial.printf("  SSID:     %s\n", AP_SSID);
  Serial.printf("  Password: %s\n", AP_PASS);
  Serial.printf("  IP:       %s ← use this in Bridge Settings\n", WiFi.softAPIP().toString().c_str());
  Serial.println("  Port:     3333\n");
  Serial.println("  → Connect your IDE laptop to the \"" AP_SSID "\" WiFi network");
  Serial.println("  → Then set Bridge IP to 192.168.4.1 in Bridge Settings\n");
#else
  Serial.println("\n╔════════════════════════════════════════════════════╗");
  Serial.println("║      ESP32 STATION MODE (STA) — Joining WiFi      ║");
  Serial.println("╚════════════════════════════════════════════════════╝");
  Serial.printf("  Connecting to: %s", STA_SSID);
  WiFi.begin(STA_SSID, STA_PASS);
  uint8_t tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n\n  ✗ Connection failed! Check WiFi credentials:");
    Serial.printf("    SSID: %s\n", STA_SSID);
    Serial.printf("    Pass: %s\n", STA_PASS);
    Serial.println("\n  Restarting...\n");
    delay(2000);
    ESP.restart();
  }
  Serial.printf("\n  ✓ Connected!\n");
  Serial.printf("  IP:       %s ← use this in Bridge Settings\n", WiFi.localIP().toString().c_str());
  Serial.printf("  SSID:     %s\n", STA_SSID);
  Serial.println("  Port:     3333\n");
  Serial.println("  → Copy the IP address above into Bridge Settings → Connection tab\n");
#endif

  tcpServer.begin();
  Serial.printf("  TCP server listening on port %d...\n\n", TCP_PORT);

  // Unique OTA/mDNS hostname: companion-XXXXXX from MAC unless the
  // user overrode OTA_HOSTNAME in config.local.h.
  resolveOtaHostname();

  // Start mDNS — broadcast this ESP32 as "<hostname>.local" on the network
  if (!MDNS.begin(otaHostname)) {
    Serial.println("  ⚠ mDNS init failed");
  } else {
    Serial.printf("  ✓ mDNS started → %s.local\n", otaHostname);
    MDNS.addService("http", "tcp", 3333);
    Serial.println("     → IDE can connect to <hostname>.local:3333\n");
  }

#if defined(ARDUINO_ARCH_ESP32)
  // ── OTA server mode (bridge firmware can be updated over WiFi) ──
  ArduinoOTA.setHostname(otaHostname);
  // String literals can't be compared in #if — check at runtime.
  if (strlen(OTA_PASSWORD) > 0) {
    ArduinoOTA.setPassword(OTA_PASSWORD);
  }
  ArduinoOTA.onStart([]() {
    Serial.println("\n  ➜ OTA update started — bridge reflashing...");
  });
  ArduinoOTA.onProgress([](unsigned int p, unsigned int t) {
    Serial.printf("  OTA %u%%\r", p * 100 / t);
  });
  ArduinoOTA.onEnd([]() {
    Serial.println("\n  ✓ OTA update complete — rebooting");
  });
  ArduinoOTA.begin();
  Serial.printf("  ✓ OTA server on port 3232 (hostname %s.local)\n", otaHostname);
  Serial.printf("  → Re-flash this bridge with: companion ota upload <ip>\n\n");
#endif
}

// ─────────────────────────────────────────────────────────────
void loop() {
#if defined(ARDUINO_ARCH_ESP32)
  ArduinoOTA.handle(); // keep the OTA server responsive
#endif
  // Accept new client if none connected
  if (!tcpClient || !tcpClient.connected()) {
    WiFiClient candidate = tcpServer.accept();
    if (candidate) {
      tcpClient = candidate;
      tcpClient.setNoDelay(true);
      ctrlLen = 0; // fresh frame boundary for the new connection
      Serial.printf("\n✓ IDE connected from: %s:%d\n", 
                    tcpClient.remoteIP().toString().c_str(), 
                    tcpClient.remotePort());
      Serial.println("  → Ready to receive upload commands\n");
    }
  }

  if (!tcpClient || !tcpClient.connected()) return;

  // ── TCP → UART (control frames parsed at frame boundary only) ──
  // Byte-wise state machine backed by ctrlBuf/ctrlLen: the magic pair
  // CTRL_A CTRL_B is only special when the parser is idle (ctrlLen==0,
  // i.e. at a frame boundary). A lone CTRL_A is held until the next
  // byte decides it; split commands accumulate across reads; firmware
  // bytes — including embedded 0xEF 0xBE — pass through untouched.
  while (tcpClient.available()) {
    int len = tcpClient.read(buf, BUF_SIZE);
    if (len <= 0) break;
    for (int i = 0; i < len; i++) {
      pumpTcpByte(buf[i]);
    }
  }

  // ── UART → TCP ───────────────────────────────────────────────
  int avail = 0;
  while (Serial2.available() && avail < BUF_SIZE) {
    buf[avail++] = (uint8_t)Serial2.read();
  }
  if (avail > 0) tcpClient.write(buf, avail);
}

// ── Control command handler ───────────────────────────────────
// Called only with a complete frame (see pumpTcpByte/ctrlFrameLength),
// so payload always holds the full cmd + args. Keeps the original
// signature; returns number of payload bytes consumed.
int handleControl(uint8_t* payload, int available) {
  if (available < 1) return 0;

  switch (payload[0]) {

    case CMD_ENTER_BOOT:
      Serial.printf("[CTRL] Enter bootloader — profile %d (%s)\n",
                    currentProfile, profiles[currentProfile].name);
      pinsBootloader();
      return 1;

    case CMD_RESET:
      Serial.println("[CTRL] Reset target");
      pinsReset();
      return 1;

    case CMD_RELEASE:
      Serial.println("[CTRL] Release pins");
      pinsRelease();
      return 1;

    case CMD_SET_BAUD:
      if (available >= 5) {
        uint32_t baud = ((uint32_t)payload[1] << 24) |
                        ((uint32_t)payload[2] << 16) |
                        ((uint32_t)payload[3] <<  8) |
                         (uint32_t)payload[4];
        currentBaud = baud;
        Serial2.begin(baud, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
        Serial.printf("[CTRL] Baud → %u\n", baud);
        return 5;
      }
      return 1;

    case CMD_SET_PROFILE:
      if (available >= 2) {
        uint8_t p = payload[1];
        uint8_t maxP = sizeof(profiles) / sizeof(profiles[0]);
        if (p < maxP) {
          currentProfile = p;
          Serial.printf("[CTRL] Profile → %d (%s)\n", p, profiles[p].name);
        }
        return 2;
      }
      return 1;

    case CMD_QUERY: {
      char resp[160];
      snprintf(resp, sizeof(resp),
               "%s profile=%d(%s) baud=%u EN=%d BOOT=%d ota=on(mdns=%s,port=3232)\r\n",
               FW_VERSION, currentProfile, profiles[currentProfile].name,
               currentBaud, PIN_TARGET_EN, PIN_TARGET_BOOT, otaHostname);
      tcpClient.print(resp);
      return 1;
    }

    default:
      Serial.printf("[CTRL] Unknown cmd: 0x%02X\n", payload[0]);
      return 1;
  }
}

// ── Pin helpers ───────────────────────────────────────────────

// Idle — target runs normally
void pinsRelease() {
  digitalWrite(PIN_TARGET_EN,   HIGH);
  digitalWrite(PIN_TARGET_BOOT, HIGH);
}

// Pulse reset
void pinsReset() {
  digitalWrite(PIN_TARGET_EN, LOW);
  delay(profiles[currentProfile].resetHoldMs);
  digitalWrite(PIN_TARGET_EN, HIGH);
}

// Assert BOOT pin then pulse reset → target starts in bootloader
void pinsBootloader() {
  const MCUProfile& p = profiles[currentProfile];
  // Drive BOOT to its active level
  digitalWrite(PIN_TARGET_BOOT, p.bootPinActiveHigh ? HIGH : LOW);
  delay(50);
  // Pulse EN/RST
  digitalWrite(PIN_TARGET_EN, LOW);
  delay(p.resetHoldMs);
  digitalWrite(PIN_TARGET_EN, HIGH);
  // Keep BOOT asserted — IDE sends CMD_RELEASE when done
}
