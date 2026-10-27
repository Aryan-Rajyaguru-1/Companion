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
 * Build with `companion compile` — the Companion CLI owns the board core,
 * toolchain, and library resolution, so no Arduino IDE or arduino-cli install
 * is required.
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
#include <mbedtls/md.h>

// ── WiFi configuration (overridable) ──────────────────────────
// config.local.h (this folder) is git-ignored. The tracked, sanitized
// template is config.example.h; copy it and fill in personal credentials.
// If the file is absent, the fail-closed defaults below are used.
#if __has_include("config.local.h")
  #include "config.local.h"
#endif

// ── Defaults (only used when config.local.h is not present) ────
// Set WIFI_AP_MODE to:
//   true  → ESP32 hosts its own Access Point (no router needed)
//           → IDE connects to the AP_SSID you configure
//           → Then use IP: 192.168.4.1 in Bridge Settings
//           → AP_PASS must be a unique 8+ character value; no default exists
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
  #define AP_PASS         ""   // MUST be set (8+ chars); the sketch refuses an open AP
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
  #define OTA_PASSWORD    ""   // MUST be set (8+ chars) to enable LAN OTA
#endif

// ── Bridge authentication (LAN mode) ──────────────────────────
// Per-device shared secret. A LAN client must prove knowledge of this key
// with an HMAC-SHA256 challenge-response before the firmware accepts control
// commands or forwards raw UART bytes. Without it the LAN TCP server stays
// OFF (fail closed) while LAN OTA remains available for recovery.
//
// Relay mode (RELAY_MODE_REMOTE=1) does not start the LAN TCP server; the
// hub's DEVICE_TOKEN and per-device secret protect that transport instead.
#ifndef BRIDGE_KEY
  #define BRIDGE_KEY      ""   // MUST be set (8+ chars) for LAN mode
#endif
// A credential is usable only when it is long enough and not a copied
// placeholder. This deliberately recognizes the old public AP default
// ("flashme!") too, so an unedited config cannot silently keep an open AP.
static bool credentialConfigured(const char *v) {
  if (v == nullptr || strlen(v) < 8) return false;
  if (strncmp(v, "YOUR_", 5) == 0) return false;
  if (strncmp(v, "CHANGE_ME", 9) == 0) return false;
  if (strcmp(v, "flashme!") == 0) return false;
  return true;
}
static bool localOtaStarted = false;
// Resolved at runtime in setup(): stays OTA_HOSTNAME when the user
// overrode it in config.local.h, otherwise becomes companion-XXXXXX
// built from the last 3 bytes of the eFuse base MAC so multiple
// bridges on one LAN get unique OTA/mDNS hostnames.
char otaHostname[32] = OTA_HOSTNAME_DEFAULT;

// Firmware version — reported in device_hello. Defined HERE, before the relay
// block that returns it: macros are textual, so the reference must already
// resolve at that point (this is why it is not in the constants section
// further down). Guarded so a build can still override it.
#ifndef FW_VERSION
  #define FW_VERSION      "OTA-BRIDGE v1.1"
#endif

// ── Remote relay link (category-2 remote: the bridge dials the hub) ──
// OPTIONAL — the default (RELAY_MODE_REMOTE 0) keeps the LAN TCP server
// above. With RELAY_MODE_REMOTE 1 the bridge dials the relay hub instead and
// pipes WS↔UART, so an IDE anywhere on the internet can flash the target
// through `companion relay bridge` (which exposes the remote bridge as a
// local TCP socket) — every LAN tool then works unchanged.
#ifndef RELAY_MODE_REMOTE
  #define RELAY_MODE_REMOTE 0
#endif
#ifndef RELAY_HOST
  #define RELAY_HOST    "YOUR_HUB_LAN_IP"  // host running `companion relay hub`
#endif
#ifndef RELAY_PORT
  #define RELAY_PORT    8931
#endif
#ifndef RELAY_TLS
  #define RELAY_TLS     false  // true → wss:// (through a TLS-terminating proxy)
#endif
#ifndef RELAY_CA_CERT
  #define RELAY_CA_CERT "YOUR_HUB_CA_PEM"  // REQUIRED when RELAY_TLS is true
#endif
#ifndef DEVICE_TOKEN
  #define DEVICE_TOKEN  "YOUR_DEVICE_TOKEN"  // COMPANION_RELAY_DEVICES_TOKEN on the hub
#endif
// DEVICE_ID_DEFAULT is the BASE name; unless config.local.h sets DEVICE_ID
// explicitly, the real id is this plus a MAC-derived suffix (resolveRelayDeviceId)
// so two boards from the same config never collide on the hub.
#define DEVICE_ID_DEFAULT "companion-bridge"
#ifndef DEVICE_ID
  #define DEVICE_ID     DEVICE_ID_DEFAULT
#endif
#ifndef RELAY_FRAME_KB
  #define RELAY_FRAME_KB 8
#endif

// The shared dial-out link (ONE copy, shared with RelayDevice): WS object,
// NVS secret, device_hello, the zombie-link watchdog (ping/pong) and the
// re-dial loop. RELAY_* above must precede this include.
//
// Its library dependencies are declared HERE on purpose: the builder
// discovers libraries by scanning the sketch's OWN sources, and headers
// under ../shared/ are outside that scan (the shared header includes them
// too; the include guards make the double include harmless). Same pattern as
// RelayDevice.ino.
#include <ArduinoJson.h>
#include <ArduinoWebsockets.h>
#include <Preferences.h>
#include "../shared/relay_link.h"

// The relay pipe: bytes from the hub are control commands and UART data in
// the SAME stream the LAN TCP client delivers — the parser is byte-wise and
// passes non-magic bytes straight to the target, so nothing changes.
//
// These callbacks are captureless lambdas in the config below, not named
// functions: Arduino's prototype generator emits prototypes for .ino
// functions BEFORE the sketch's includes, where WebsocketsMessage does not
// exist yet. The generated prototype then breaks the build. Lambdas are not
// auto-prototyped, and this forward declaration lets them call the parser.
void pumpTcpByte(uint8_t b);

static const char *bridgeFwVersion() { return FW_VERSION; }
static bool bridgeNeverPushing() { return false; } // the bridge is never an OTA target here

// resolveRelayDeviceId decides what this board calls itself on the hub. An
// explicit DEVICE_ID in config.local.h always wins; the DEFAULT is suffixed
// from the MAC, exactly like the LAN OTA hostname. A fixed literal default is
// not cosmetic here: two boards flashed from the example config would take the
// same id, and since re-registration supersedes the incumbent, they would
// flip-flop forever — each side closing the other every 5s as its watchdog
// re-dials.
#if RELAY_MODE_REMOTE
static void resolveRelayDeviceId() {
  if (strcmp(DEVICE_ID, DEVICE_ID_DEFAULT) != 0) {
    strlcpy(relayDeviceId, DEVICE_ID, sizeof(relayDeviceId));
    return;
  }
  char suffix[7];
  relayMacSuffix(suffix, sizeof(suffix)); // shared helper from CompanionRelay.h
  snprintf(relayDeviceId, sizeof(relayDeviceId), "%s-%s", DEVICE_ID_DEFAULT, suffix);
}
#endif

static const RelayLinkConfig bridgeRelayLink = {
  bridgeFwVersion,
  bridgeNeverPushing,   // the watchdog never stands down — always on
  // push_start/status frames don't apply to a transparent bridge; ignore.
  [](const String &t) { (void)t; },
  [](WebsocketsMessage &msg) {
    const uint8_t *p = (const uint8_t *)msg.c_str();
    size_t n = msg.length();
    for (size_t i = 0; i < n; i++) {
      pumpTcpByte(p[i]); // same parser: control frames parsed, UART passes through
    }
  },
};
void resolveOtaHostname() {
  if (strcmp(OTA_HOSTNAME, OTA_HOSTNAME_DEFAULT) != 0) {
    strncpy(otaHostname, OTA_HOSTNAME, sizeof(otaHostname) - 1);
    otaHostname[sizeof(otaHostname) - 1] = '\0';
    return;
  }
  char suffix[7];
  relayMacSuffix(suffix, sizeof(suffix)); // shared helper from CompanionRelay.h
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
// FW_VERSION is defined near the top of this sketch (the relay block reports
// it in device_hello, and macros are textual — the reference must resolve
// before that point).

// ── Control protocol (matches bridge-client.js) ───────────────
#define CTRL_A              0xEF
#define CTRL_B              0xBE
#define CMD_ENTER_BOOT      0x01
#define CMD_RESET           0x02
#define CMD_RELEASE         0x03
#define CMD_SET_BAUD        0x10   // + 4 bytes uint32 big-endian
#define CMD_SET_PROFILE     0x11   // + 1 byte profile index
#define CMD_QUERY           0x20
// Authentication (LAN mode only). The client sends AUTH_BEGIN, the bridge
// replies with a fresh 32-byte nonce, and the client returns
// HMAC-SHA256(BRIDGE_KEY, nonce). No control command or raw UART byte is
// accepted before AUTH_OK.
#define CMD_AUTH_BEGIN      0x30   // client → bridge
#define CMD_AUTH_RESPONSE   0x31   // client → bridge + 32-byte HMAC
#define CMD_AUTH_CHALLENGE  0x32   // bridge → client + 32-byte nonce
#define CMD_AUTH_OK         0x33   // bridge → client
#define CMD_AUTH_FAIL       0x34   // bridge → client
#define AUTH_NONCE_LEN      32
#define AUTH_PROBE_WINDOW_MS 5000  // close a client that never authenticates
#define AUTH_FAIL_HOLD_MS    500   // let the client read AUTH_FAIL before close

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
bool clientWasConnected = false; // edge-detect: release target pins on disconnect
uint8_t    buf[BUF_SIZE];

// ── Control-frame parser state (persistent across loop() reads) ──
// Frame format: CTRL_A CTRL_B <cmd byte + args>. The magic pair is
// only special at a frame boundary (parser idle); inside the payload
// or between split reads, raw 0xEF 0xBE bytes pass through untouched.
// Incomplete reads are buffered here until the full command arrives.
#define CTRL_FRAME_MAX  40  // longest command: magic(2)+AUTH_RESPONSE(1+32)
uint8_t  ctrlBuf[CTRL_FRAME_MAX];
uint8_t  ctrlLen = 0;       // bytes buffered in ctrlBuf (0 = idle)

// ── LAN authentication state ─────────────────────────────────
// lanAuthRequired is set only when the LAN TCP server is enabled (i.e. the
// bridge is not in relay mode and BRIDGE_KEY is configured). Relay mode keeps
// the historical unauthenticated pipe: the hub already authenticates the
// device and the remote client.
bool     lanAuthRequired  = false;
bool     lanAuthenticated = false;
bool     lanBridgeEnabled = false;
bool     authChallengeSent = false;
bool     authFailed        = false; // terminal for this connection
uint8_t  authNonce[AUTH_NONCE_LEN];
uint32_t authDeadline  = 0;
uint32_t authFailureAt = 0;

// Forward declarations (Arduino generates prototypes, but be explicit).
int handleControl(uint8_t* payload, int available);
int ctrlFrameLength(uint8_t cmd);
static void sendAuthChallenge();
static void verifyAuthResponse(uint8_t* payload, int available);

// Total payload bytes (cmd byte + args) a command needs.
// Returns 0 only if cmd byte not yet known (never called that way).
int ctrlFrameLength(uint8_t cmd) {
  switch (cmd) {
    case CMD_SET_BAUD:      return 5;  // cmd + 4-byte big-endian baud
    case CMD_SET_PROFILE:   return 2;  // cmd + 1-byte index
    case CMD_AUTH_RESPONSE: return 1 + AUTH_NONCE_LEN; // cmd + HMAC
    case CMD_ENTER_BOOT:
    case CMD_RESET:
    case CMD_RELEASE:
    case CMD_QUERY:
    case CMD_AUTH_BEGIN:
    default:                return 1;  // single-byte commands; unknown too
  }
}

// True while a LAN client still has to authenticate. Relay mode leaves
// lanAuthRequired false, so the transparent relay pipe is unchanged.
static bool authBlocksRaw() {
  return lanAuthRequired && !lanAuthenticated;
}

// Feed one TCP byte through the frame parser.
void pumpTcpByte(uint8_t b) {
  if (ctrlLen == 0) {
    // Frame boundary: only here is CTRL_A potentially magic.
    if (b == CTRL_A) { ctrlBuf[0] = b; ctrlLen = 1; return; }
    if (authBlocksRaw()) return; // no raw UART bytes before authentication
    Serial2.write(b);
    return;
  }
  if (ctrlLen == 1) {
    // Held a lone CTRL_A; this byte decides.
    if (b == CTRL_B) { ctrlBuf[1] = b; ctrlLen = 2; return; }
    // Before authentication, discard the held byte even if the frame turns
    // out to be a false alarm. It must never reach the target.
    if (authBlocksRaw()) { ctrlLen = 0; return; }
    Serial2.write(CTRL_A); // false alarm — flush held byte
    if (b == CTRL_A) { ctrlBuf[0] = b; ctrlLen = 1; } // re-hold, stay armed
    else { ctrlLen = 0; Serial2.write(b); }
    return;
  }
  // Inside a frame: accumulate (never scan for magic here).
  if (ctrlLen >= CTRL_FRAME_MAX) {
    // Should be unreachable (longest frame is 2 + 34 = 36 bytes); fail safe by
    // dropping pre-auth bytes and restarting from this byte.
    if (!authBlocksRaw()) Serial2.write(ctrlBuf, ctrlLen);
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
#if RELAY_MODE_REMOTE
  // Relay mode: the bridge DIALS the hub, so it must join the router (STA).
  WiFi.mode(WIFI_STA);
  WiFi.begin(STA_SSID, STA_PASS);
  Serial.printf("\n  [relay] joining %s", STA_SSID);
  uint8_t tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500); Serial.print("."); tries++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n\n  ✗ WiFi failed! Check STA_SSID/STA_PASS in config.local.h");
    delay(2000);
    ESP.restart();
  }
  Serial.printf("\n  ✓ Connected! ip=%s\n", WiFi.localIP().toString().c_str());
#elif WIFI_AP_MODE
  if (!credentialConfigured(AP_PASS)) {
    Serial.println("\n  ✗ REFUSING TO START AN OPEN ACCESS POINT");
    Serial.println("    Set AP_PASS in config.local.h to a unique password of at least 8 characters.");
    Serial.println("    The old public default (\"flashme!\") is not accepted.\n");
    return; // no AP, no OTA, no bridge service
  }
  WiFi.softAP(AP_SSID, AP_PASS);
  Serial.println("\n╔════════════════════════════════════════════════════╗");
  Serial.println("║         ESP32 ACCESS POINT MODE (AP)              ║");
  Serial.println("╚════════════════════════════════════════════════════╝");
  Serial.printf("  SSID:     %s\n", AP_SSID);
  // The AP password is a credential too; report that it is configured
  // without disclosing it.
  Serial.println("  Password: <set in config.local.h>");
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
    // Never print the WiFi password: serial output ends up in photos, logs
    // and pasted bug reports.
    Serial.println("    Pass: <set in config.local.h>");
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

  // Unique OTA/mDNS hostname: companion-XXXXXX from MAC unless the user
  // overrode OTA_HOSTNAME in config.local.h. Resolve it in BOTH modes: the LAN
  // OTA recovery service is also available when the bridge dials the relay.
  resolveOtaHostname();

#if RELAY_MODE_REMOTE
  // Relay mode: dial the hub and pipe WS↔UART. No LAN TCP server, no mDNS —
  // the IDE reaches this bridge through `companion relay bridge`.
  resolveRelayDeviceId();      // MAC-suffixed unless config.local.h set DEVICE_ID
  relayBegin(bridgeRelayLink); // secret + callbacks + dial the hub
  Serial.println("  → relay link up: flashing through the hub (no LAN server)\n");
#else
  // LAN bridge security: the TCP server accepts control commands and raw
  // target bytes only after a successful HMAC challenge-response. A bridge
  // without BRIDGE_KEY does NOT start the server (fail closed); LAN OTA below
  // still starts when OTA_PASSWORD is configured, so the device can be
  // reflashed over WiFi instead of becoming unreachable.
  lanAuthRequired = credentialConfigured(BRIDGE_KEY);
  lanBridgeEnabled = lanAuthRequired;

  if (lanBridgeEnabled) {
    tcpServer.begin();
    Serial.printf("  TCP server listening on port %d (HMAC-SHA256 auth)...\n\n", TCP_PORT);
  } else {
    Serial.println("  ⚠ LAN bridge TCP server DISABLED: BRIDGE_KEY is not set.");
    Serial.println("    Add a unique BRIDGE_KEY (8+ chars) to config.local.h and");
    Serial.println("    reflash. Relay mode uses DEVICE_TOKEN instead.");
    Serial.println();
  }

  // Start mDNS — broadcast this ESP32 as "<hostname>.local" on the network
  if (!MDNS.begin(otaHostname)) {
    Serial.println("  ⚠ mDNS init failed");
  } else {
    Serial.printf("  ✓ mDNS started → %s.local\n", otaHostname);
    if (lanBridgeEnabled) {
      MDNS.addService("http", "tcp", 3333);
      Serial.println("     → IDE can connect to <hostname>.local:3333\n");
    }
  }
#endif // RELAY_MODE_REMOTE / LAN server

  // OTA has no unauthenticated mode: an empty/placeholder/published default
  // password disables the service. This is fail-closed by design — the old
  // behavior started ArduinoOTA with no password and merely printed a warning,
  // so anyone on the network could reflash the bridge.
#if defined(ARDUINO_ARCH_ESP32)
  if (!credentialConfigured(OTA_PASSWORD)) {
    Serial.println("  ⚠ LAN OTA disabled: set OTA_PASSWORD in config.local.h");
    Serial.println("    to a unique password of at least 8 characters.\n");
  } else {
    // ── OTA server mode (bridge firmware can be updated over WiFi) ──
    ArduinoOTA.setHostname(otaHostname);
    ArduinoOTA.setPassword(OTA_PASSWORD);
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
    localOtaStarted = true;
    Serial.printf("  ✓ OTA server on port 3232 (hostname %s.local)\n", otaHostname);
    Serial.printf("  → Re-flash this bridge with: companion ota upload <ip>\n\n");
  }
#endif
}

// ─────────────────────────────────────────────────────────────
// ── Client transport ──────────────────────────────────────────
// The ONE place bytes leave for the client that is driving the target.
// LAN mode writes to the TCP socket; RELAY_MODE_REMOTE writes to the paired
// relay connection. Both share the same byte parser (pumpTcpByte) and the
// same control replies, so they MUST share the writer too — an early version
// of remote mode registered and paired but never forwarded a byte, because the
// UART path had a TCP-only writer and loop() returned before it.
static void bridgeWriteToClient(const uint8_t *p, size_t n) {
#if RELAY_MODE_REMOTE
  relaySendBinary(p, n);
#else
  if (tcpClient && tcpClient.connected()) tcpClient.write(p, n);
#endif
}

static void bridgeWriteToClient(const char *s) {
  bridgeWriteToClient((const uint8_t *)s, strlen(s));
}

void loop() {
#if defined(ARDUINO_ARCH_ESP32)
  if (localOtaStarted) ArduinoOTA.handle(); // keep the OTA server responsive
#endif

#if RELAY_MODE_REMOTE
  // ── Remote mode: the relay IS the transport ─────────────────────
  // relayLinkLoop() polls the socket, runs the zombie-link watchdog and
  // re-dials — it was missing here, so the board registered, paired, and then
  // sat on a socket it never read or wrote. The incoming side (hub → UART)
  // is the onBinary callback; the outgoing side is here.
  relayLinkLoop();

  // ── UART → client (relay) ─────────────────────────────────────
  int avail = 0;
  while (Serial2.available() && avail < BUF_SIZE) {
    buf[avail++] = (uint8_t)Serial2.read();
  }
  if (avail > 0) bridgeWriteToClient(buf, avail);
#else
  // No LAN server when BRIDGE_KEY is missing. Keep OTA responsive above.
  if (!lanBridgeEnabled) return;

  // Accept new client if none connected
  if (!tcpClient || !tcpClient.connected()) {
    WiFiClient candidate = tcpServer.accept();
    if (candidate) {
      tcpClient = candidate;
      tcpClient.setNoDelay(true);
      ctrlLen = 0; // fresh frame boundary for the new connection
      // Fresh authentication session: new nonce, no inherited approval.
      lanAuthenticated = false;
      authChallengeSent = false;
      authFailed = false;
      authFailureAt = 0;
      authDeadline = millis() + AUTH_PROBE_WINDOW_MS;
      for (size_t i = 0; i < AUTH_NONCE_LEN; i++) {
        authNonce[i] = (uint8_t)esp_random();
      }
      Serial.printf("\n✓ IDE connected from: %s:%d\n",
                    tcpClient.remoteIP().toString().c_str(),
                    tcpClient.remotePort());
      Serial.println(lanAuthRequired
        ? "  → Awaiting HMAC authentication\n"
        : "  → Ready to receive upload commands\n");
    }
  }

  if (!tcpClient || !tcpClient.connected()) {
    // A client that vanished mid-session — esptool died, the IDE crashed, the
    // WiFi dropped — used to leave EN/BOOT exactly as the last command set
    // them, so an ESP32 target stayed in download mode until someone pressed
    // RESET by hand. Release the pins on the EDGE of the disconnect (not every
    // loop iteration, which would hammer the target with resets).
    if (clientWasConnected) {
      Serial.println("[bridge] client disconnected — releasing target pins");
      pinsRelease();
      clientWasConnected = false;
      lanAuthenticated = false;
      authChallengeSent = false;
      authFailed = false;
      authDeadline = 0;
      authFailureAt = 0;
    }
    return;
  }
  clientWasConnected = true;

  // Close clients that fail authentication or never start the handshake.
  // AUTH_FAIL is sent immediately; the short hold lets the peer read it.
  if (authBlocksRaw()) {
    if (authFailed && (millis() - authFailureAt) > AUTH_FAIL_HOLD_MS) {
      Serial.println("[AUTH] Closing client after failed authentication");
      tcpClient.stop();
      authFailureAt = 0;
      authDeadline = 0;
      return;
    }
    if (authDeadline && (int32_t)(millis() - authDeadline) >= 0) {
      Serial.println("[AUTH] Closing client: authentication timeout");
      tcpClient.stop();
      authDeadline = 0;
      return;
    }
  }

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
  // Do not leak target output to an unauthenticated LAN client. The HMAC
  // handshake only uses TCP, so drop target bytes until AUTH_OK.
  int avail = 0;
  while (Serial2.available() && avail < BUF_SIZE) {
    buf[avail++] = (uint8_t)Serial2.read();
  }
  if (avail > 0 && !authBlocksRaw()) bridgeWriteToClient(buf, avail);
#endif // RELAY_MODE_REMOTE
}

// ── LAN authentication helpers ────────────────────────────────
// HMAC-SHA256(BRIDGE_KEY, nonce). mbedTLS is part of the ESP32 Arduino core.
static bool hmacSha256(const uint8_t* key, size_t keyLen,
                       const uint8_t* data, size_t dataLen,
                       uint8_t out[AUTH_NONCE_LEN]) {
  const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr) return false;
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  bool ok = mbedtls_md_setup(&ctx, info, 1) == 0 &&
            mbedtls_md_hmac_starts(&ctx, key, keyLen) == 0 &&
            mbedtls_md_hmac_update(&ctx, data, dataLen) == 0 &&
            mbedtls_md_hmac_finish(&ctx, out) == 0;
  mbedtls_md_free(&ctx);
  return ok;
}

// Constant-time comparison for authentication tags. Do not replace with
// memcmp: tag comparison must not leak how many leading bytes matched.
static bool constantTimeEqual(const uint8_t* a, const uint8_t* b, size_t n) {
  uint8_t diff = 0;
  for (size_t i = 0; i < n; i++) diff |= (uint8_t)(a[i] ^ b[i]);
  return diff == 0;
}

static void sendAuthFrame(uint8_t cmd, const uint8_t* payload, size_t n) {
  uint8_t hdr[3] = {CTRL_A, CTRL_B, cmd};
  bridgeWriteToClient(hdr, sizeof(hdr));
  if (n > 0) bridgeWriteToClient(payload, n);
}

// Mark this connection's authentication as permanently failed. No second
// attempt is accepted: a peer cannot keep guessing, rotate the nonce, or
// extend the handshake window on the same TCP connection.
static void failAuth() {
  authFailed = true;
  authChallengeSent = false;
  authFailureAt = millis();
  authDeadline = 0;
  sendAuthFrame(CMD_AUTH_FAIL, nullptr, 0);
}

// Send a fresh challenge. Only the FIRST AUTH_BEGIN gets a nonce: repeated
// begins used to rotate the nonce and push the deadline forward forever, so an
// unauthenticated peer could hold a connection open indefinitely.
static void sendAuthChallenge() {
  if (authFailed || authChallengeSent) return;
  for (size_t i = 0; i < AUTH_NONCE_LEN; i++) {
    authNonce[i] = (uint8_t)esp_random();
  }
  authChallengeSent = true;
  authDeadline = millis() + AUTH_PROBE_WINDOW_MS;
  sendAuthFrame(CMD_AUTH_CHALLENGE, authNonce, AUTH_NONCE_LEN);
  Serial.println("[AUTH] Challenge sent");
}

static void verifyAuthResponse(uint8_t* payload, int available) {
  if (authFailed) return; // failure is terminal for this connection
  if (!authChallengeSent || available < 1 + AUTH_NONCE_LEN) {
    Serial.println("[AUTH] Response without a live challenge");
    failAuth();
    return;
  }

  uint8_t expected[AUTH_NONCE_LEN];
  const uint8_t* key = (const uint8_t*)BRIDGE_KEY;
  size_t keyLen = strlen(BRIDGE_KEY);
  if (!hmacSha256(key, keyLen, authNonce, AUTH_NONCE_LEN, expected) ||
      !constantTimeEqual(expected, payload + 1, AUTH_NONCE_LEN)) {
    Serial.println("[AUTH] Rejected: bad bridge key");
    failAuth();
    return;
  }

  lanAuthenticated = true;
  authChallengeSent = false;
  authFailed = false;
  authDeadline = 0;
  authFailureAt = 0;
  sendAuthFrame(CMD_AUTH_OK, nullptr, 0);
  Serial.println("[AUTH] Client authenticated");
}

// ── Control command handler ───────────────────────────────────
// Called only with a complete frame (see pumpTcpByte/ctrlFrameLength),
// so payload always holds the full cmd + args. Keeps the original
// signature; returns number of payload bytes consumed.
int handleControl(uint8_t* payload, int available) {
  if (available < 1) return 0;

  // LAN gate: before authentication only the handshake is accepted. Every
  // other command is dropped (and never reaches the target).
  if (lanAuthRequired) {
    if (!lanAuthenticated) {
      if (payload[0] == CMD_AUTH_BEGIN) {
        sendAuthChallenge();
        return 1;
      }
      if (payload[0] == CMD_AUTH_RESPONSE) {
        verifyAuthResponse(payload, available);
        return 1 + AUTH_NONCE_LEN;
      }
      Serial.printf("[AUTH] Ignored cmd 0x%02X before authentication\n", payload[0]);
      return ctrlFrameLength(payload[0]);
    }
    // A repeated handshake after success is harmless but unnecessary.
    if (payload[0] == CMD_AUTH_BEGIN || payload[0] == CMD_AUTH_RESPONSE) {
      return ctrlFrameLength(payload[0]);
    }
  }

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
        Serial.printf("[CTRL] Baud → %lu\n", (unsigned long)baud);
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
               "%s profile=%d(%s) baud=%lu EN=%d BOOT=%d ota=on(mdns=%s,port=3232)\r\n",
               FW_VERSION, currentProfile, profiles[currentProfile].name,
               (unsigned long)currentBaud, PIN_TARGET_EN, PIN_TARGET_BOOT, otaHostname);
      bridgeWriteToClient(resp); // same transport as the client's own bytes
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
