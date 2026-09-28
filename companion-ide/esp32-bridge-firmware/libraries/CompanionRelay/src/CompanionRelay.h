// CompanionRelay.h — dial-out relay updates for ANY ESP32 sketch.
//
// This is the ONE implementation of the link: the first-party sketches
// (RelayDevice, esp32_bridge) include the very same file from
// esp32-bridge-firmware/shared/relay_link.h, and a third-party sketch uses the
// library form below. One contract, one implementation, no drift.
//
// The sketch configures it with a RelayLinkConfig (callback pointers, so no
// name-based prototype conflicts with Arduino's auto-generated prototypes):
//
//   version    — the firmware version string reported in device_hello
//   onText     — a TEXT frame from the hub (control/protocol; the heartbeat
//                pong is consumed internally first)
//   onBinary   — a BINARY frame from the hub (OTA bytes / UART data)
//
// ── Library form ────────────────────────────────────────────────────
// Copy this into your sketch folder as CompanionRelay.h, or install the
// library (companion-ide/esp32-bridge-firmware/libraries/CompanionRelay).
// Then, in your own sketch:
//
//   #include <CompanionRelay.h>
//
//   void onRelayFrame(uint8_t *data, size_t n) { /* the pushed bytes */ }
//   void onRelayCommand(const char *kind)      { /* "start", "done", ... */ }
//
//   void setup() {
//     CompanionRelayConfig cfg;
//     cfg.wifiSSID = "your-ssid";  cfg.wifiPassword = "your-pass";
//     cfg.relayHost = "ota.example.com"; cfg.relayPort = 443; cfg.relayTLS = true;
//     cfg.deviceToken = "<COMPANION_RELAY_DEVICES_TOKEN>";
//     cfg.deviceId = "esp32-node-01";     // unique per board
//     cfg.onFrame = onRelayFrame;         // required: receives the pushed image
//     cfg.onCommand = onRelayCommand;     // optional: push_start / push_done
//     CompanionRelay.begin(cfg);           // joins WiFi, then dials the hub
//   }
//   void loop() { CompanionRelay.loop(); /* …or relayLinkLoop(); */ }
//
// Everything below is that implementation: the same link the two first-party
// sketches use, so a third-party sketch behaves identically.
//
// The board dials the hub OUTBOUND (wss://host:port/device?token=...), so no
// inbound ports are needed anywhere, and the zombie-link watchdog (ping/pong,
// answered by the hub) re-dials when a connection dies without a close frame.

#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <ArduinoWebsockets.h>
#include <Preferences.h>
#include <esp_system.h>

using namespace websockets;

struct RelayLinkConfig {
  const char *(*version)();
  bool (*pushActive)(); // true while an OTA push streams (the watchdog stands down)
  void (*onText)(const String &t);
  void (*onBinary)(WebsocketsMessage &msg);
};

// ── Configuration defaults ──────────────────────────────────────────
// Inert when a sketch does not define them, so this header compiles STANDALONE
// (the CompanionRelay library form) as well as inside the first-party sketches
// (which define them in config.local.h BEFORE including the link).
#ifndef RELAY_HOST
  #define RELAY_HOST     "YOUR_RELAY_HOST"
#endif
#ifndef RELAY_PORT
  #define RELAY_PORT     8931
#endif
#ifndef RELAY_TLS
  #define RELAY_TLS      false
#endif
#ifndef DEVICE_TOKEN
  #define DEVICE_TOKEN   "YOUR_DEVICE_TOKEN"
#endif
#ifndef DEVICE_ID
  #define DEVICE_ID      "companion-board"
#endif
#ifndef FW_VERSION
  #define FW_VERSION     "1.0.0"
#endif

// RELAY_FRAME_KB: the negotiated data-frame size the board advertises at
// hello (KiB). The hub relays it to the agent in push_ack, which then sends
// frames this big — the stop-and-wait chunk÷RTT lever. 8 KiB is the proven
// ceiling (one onMessage callback per frame).
#ifndef RELAY_FRAME_KB
  #define RELAY_FRAME_KB 8
#endif

static WebsocketsClient relayWs;
static RelayLinkConfig relayCfg = {nullptr, nullptr, nullptr};
static bool relayWsConnected = false;
static unsigned long relayLastDialAttempt = 0;
static unsigned long relayLastPingSent = 0;
static unsigned long relayLastPong = 0;
static bool relayAwaitingPong = false;
static char relayDeviceSecret[33] = {0}; // per-board identity, NVS-provisioned once

// relayDeviceId is what device_hello reports. It is a RUNTIME value, not the
// DEVICE_ID macro, because a sketch may derive it (e.g. from the MAC) so two
// boards flashed from the same example config cannot supersede each other on
// the hub. The sketch MUST set it before relayBegin().
static char relayDeviceId[48] = {0};

// ── Library-form runtime state ───────────────────────────────────────
// The implementation reads RELAY_* macros (so the two first-party sketches stay
// configured by config.local.h). The library form has no macros, so these
// values override them when non-empty. One implementation, two front doors.
static const char *relayWiFiSSID      = "";
static const char *relayWiFiPassword  = "";
static const char *relayHostOverride  = "";
static const char *relayTokenOverride = "";
static int         relayPortOverride  = 0;
static int         relayTLSOverride   = -1; // -1 unset, 0/1 explicit

// macSuffix fills out with six hex characters from the last 3 MAC bytes.
static void relayMacSuffix(char *out, size_t outLen) {
  String mac = WiFi.macAddress();
  const int pick[6] = {9, 10, 12, 13, 15, 16};
  size_t n = 0;
  for (int i = 0; i < 6 && n + 1 < outLen; i++) {
    int idx = pick[i];
    char c = (idx < (int)mac.length()) ? mac.charAt(idx) : '0';
    if (c == ':') c = '0';
    if (c >= 'a' && c <= 'f') c = (char)(c - 'a' + 'A');
    out[n++] = c;
  }
  out[n] = '\0';
}

static const char *relayLibraryVersion() { return FW_VERSION; }
static bool relayNeverPushing() { return false; } // no OTA state machine here
static void relayNoText(const String &) {}         // control frames unused

// relayLibraryFrame feeds the pushed bytes to the sketch.
static void relayLibraryFrame(WebsocketsMessage &msg) {
  const uint8_t *p = (const uint8_t *)msg.c_str();
  extern void companionRelayDispatchFrame(uint8_t *data, size_t n);
  companionRelayDispatchFrame((uint8_t *)p, msg.length());
}

// companionRelayDispatchFrame is a weak-ish hook the sketch can define to
// receive frames without a function-pointer dance. Default: drop them.
__attribute__((weak)) void companionRelayDispatchFrame(uint8_t *data, size_t n) {
  (void)data; (void)n;
}

static bool relaySendText(const String &s) { return relayWs.send(s); }

static bool relaySendBinary(const void *p, size_t len) {
  return relayWs.sendBinary((const uint8_t *)p, len);
}

static void relaySendStatus(const char *msg) {
  StaticJsonDocument<192> d;
  d["kind"] = "status";
  d["msg"] = msg;
  String out; serializeJson(d, out);
  relaySendText(out);
}

// relayLoadOrCreateSecret: first boot generates 16 random bytes via the
// hardware RNG, stores them in NVS, and prints them so they can be registered.
// Later boots read the same value back and ALSO print it, tagged "(stored)" —
// deliberate: re-flashing or re-provisioning a board should never require an
// NVS erase to recover the secret, and serial is a local, physical channel.
// The printed value is the board's identity: the hub refuses a push or a pipe
// to a device whose secret does not match, which is what stops one compromised
// agent from talking to every board on the relay.
static void relayLoadOrCreateSecret() {
  Preferences prefs;
  prefs.begin("relay", true); // read-only first
  String saved = prefs.getString("secret", "");
  prefs.end();
  if (saved.length() >= 16) {
    strlcpy(relayDeviceSecret, saved.c_str(), sizeof(relayDeviceSecret));
    Serial.printf("[relay] device secret (stored): %s\n", relayDeviceSecret);
    return;
  }
  uint8_t raw[16];
  for (int i = 0; i < 16; i += 4) {
    uint32_t r = esp_random();
    memcpy(raw + i, &r, 4);
  }
  const char *hexd = "0123456789abcdef";
  for (int i = 0; i < 16; i++) {
    relayDeviceSecret[2 * i] = hexd[(raw[i] >> 4) & 0xF];
    relayDeviceSecret[2 * i + 1] = hexd[raw[i] & 0xF];
  }
  relayDeviceSecret[32] = 0;
  prefs.begin("relay", false);
  prefs.putString("secret", relayDeviceSecret);
  prefs.end();
  Serial.println("[relay] *** FIRST BOOT: device secret provisioned ***");
  Serial.printf("[relay] *** SECRET: %s ***\n", relayDeviceSecret);
  Serial.println("[relay] *** copy it now: fleet register --secret-stdin / COMPANION_RELAY_DEVICE_SECRET ***");
}

// relayDial opens the relay link and sends device_hello (carrying the secret
// and the negotiated frame size).
static bool relayDial() {
  relayLastDialAttempt = millis();
  // A fresh link starts with no outstanding ping: without this reset a pong
  // timer left over from the DEAD link can fire against the new one and kill a
  // perfectly healthy connection seconds after it came up.
  relayAwaitingPong = false;
  relayLastPingSent = 0;
  // Library-form overrides win when set; otherwise the RELAY_* macros (which
  // the two first-party sketches get from config.local.h).
  const char *host  = relayHostOverride[0]  ? relayHostOverride  : RELAY_HOST;
  const char *token = relayTokenOverride[0] ? relayTokenOverride : DEVICE_TOKEN;
  int port  = relayPortOverride > 0 ? relayPortOverride : RELAY_PORT;
  bool tls  = relayTLSOverride >= 0 ? (relayTLSOverride == 1) : (bool)RELAY_TLS;
  String url = String(tls ? "wss://" : "ws://") + host + ":" +
               String(port) + "/device?token=" + token;
  Serial.printf("[relay] dialing %s ...\n", url.c_str());
  if (!relayWs.connect(url)) {
    Serial.println("[relay] ws connect FAILED — retrying in 5s");
    return false;
  }
  if (relayDeviceId[0] == '\0') {
    strlcpy(relayDeviceId, DEVICE_ID, sizeof(relayDeviceId));
  }
  StaticJsonDocument<320> hello;
  hello["kind"] = "device_hello";
  hello["id"] = relayDeviceId;
  hello["version"] = relayCfg.version ? relayCfg.version() : "unknown";
  hello["secret"] = relayDeviceSecret;
  hello["frame_kb"] = RELAY_FRAME_KB;
  // The board's LAN address. The relay is one-way (the board dials out), so
  // this is the ONLY way an operator learns where a board is on its own
  // network — which is exactly what the LAN recovery path
  // (`companion ota upload <ip> --ota-mode local`) needs, and what mDNS
  // discovery cannot always supply across a routed network.
  hello["ip"] = WiFi.localIP().toString();
  String out; serializeJson(hello, out);
  relaySendText(out);
  relayWsConnected = true;
  Serial.printf("[relay] registered as %s — waiting for pushes\n", relayDeviceId);
  return true;
}
// relayOnEvt tracks link state so relayLinkLoop can re-dial after a drop.
static void relayOnEvt(WebsocketsEvent e, String data) {
  (void)data;
  switch (e) {
    case WebsocketsEvent::ConnectionOpened:
      relayWsConnected = true;
      Serial.println("[relay] link open");
      break;
    case WebsocketsEvent::ConnectionClosed:
      relayWsConnected = false;
      relayAwaitingPong = false; // no pong can arrive on a closed link
      Serial.println("[relay] link closed — will re-dial");
      break;
    default:
      break;
  }
}

static void relayDispatch(WebsocketsMessage msg) {
  if (msg.isText()) {
    String t = msg.data();
    // Heartbeat reply from the hub: the link is proven alive end-to-end.
    // Match on the PARSED kind, not a substring: indexOf("pong") would also
    // accept any future text frame that merely contains those letters (a
    // status message, an error body) and call a dead link healthy.
    StaticJsonDocument<128> doc;
    if (deserializeJson(doc, t) == DeserializationError::Ok) {
      const char *kind = doc["kind"] | "";
      if (kind[0] && strcmp(kind, "pong") == 0) {
        relayAwaitingPong = false;
        relayLastPong = millis();
        return;
      }
    }
    if (relayCfg.onText) relayCfg.onText(t);
    return;
  }
  if (relayCfg.onBinary) relayCfg.onBinary(msg);
}

// relayBegin wires the callbacks, provisions the secret and dials. Call from
// setup() after WiFi is up.
static void relayBegin(const RelayLinkConfig &cfg) {
  relayCfg = cfg;
  relayLoadOrCreateSecret();
  relayWs.onMessage(relayDispatch);
  relayWs.onEvent(relayOnEvt);
  relayDial();
}

// relayLinkLoop: call from loop() — poll, the zombie-link watchdog and the
// re-dial backoff. The sketch's own loop body (LED, UART, OTA) runs after it.
//
// The watchdog: wsConnected is only cleared by the ConnectionClosed event,
// but a connection can die WITHOUT one (tunnel QUIC drop, hub crash, NAT
// timeout) — the board then sits on a dead socket reporting link=1 while no
// push can ever reach it. So ping the hub every 15s (idle only — never
// mid-push, where the ACK channel is the liveness signal) and demand a pong
// within 10s: a failed send or a missing pong proves the link is dead
// end-to-end; abandon it and re-dial.
static void relayLinkLoop() {
  relayWs.poll();

  if (!relayWsConnected && millis() - relayLastDialAttempt > 5000) {
    relayDial();
  }

  if (relayWsConnected && !(relayCfg.pushActive && relayCfg.pushActive())) {
    if (!relayAwaitingPong && millis() - relayLastPingSent > 15000) {
      relayLastPingSent = millis();
      relayAwaitingPong = true;
      if (!relaySendText("{\"kind\":\"ping\"}")) {
        Serial.println("[relay] ping write FAILED — link is dead, re-dialing");
        relayWsConnected = false;
        relayAwaitingPong = false;
        relayWs.close();
      }
    } else if (relayAwaitingPong && millis() - relayLastPingSent > 10000) {
      Serial.println("[relay] no pong in 10s — zombie link, re-dialing");
      relayWsConnected = false;
      relayAwaitingPong = false;
      relayWs.close();
    }
  } else if (relayCfg.pushActive && relayCfg.pushActive()) {
    relayAwaitingPong = false; // a push's ACK channel is the liveness signal
  }
}

// ── Public API ───────────────────────────────────────────────────────

// CompanionRelayConfig is what a sketch fills in. Every field is explicit so a
// third-party sketch has no hidden magic; the zero value is safe because
// begin() refuses to dial with an empty host or device id.
struct CompanionRelayConfig {
  const char *wifiSSID;
  const char *wifiPassword;
  const char *relayHost;
  int         relayPort;
  bool        relayTLS;
  const char *deviceToken;
  const char *deviceId;   // unique per board
  // onFrame receives the pushed image in ArduinoOTA data-phase framing. It is
  // REQUIRED: without it a push would be accepted and then dropped silently.
  void (*onFrame)(uint8_t *data, size_t n);
  // onCommand reports control frames ("start", "done"); optional.
  void (*onCommand)(const char *kind);
};

// The namespace object the README and the example sketch use.
struct CompanionRelayAPI {
  // begin provisions the per-board secret, joins WiFi, then dials the hub.
  // Returns false if WiFi or the hub could not be reached — the sketch should
  // keep running (and the watchdog will retry), not halt.
  bool begin(const CompanionRelayConfig &cfg) {
    if (cfg.onFrame == nullptr) {
      Serial.println("[relay] cfg.onFrame is required — a push would be dropped");
      return false;
    }
    // The header is a copy of relay_link.h, which reads the RELAY_* macros.
    // Rather than require a preprocessor dance on the user, map the struct
    // onto the macros the implementation already uses.
    relayWiFiSSID     = cfg.wifiSSID;
    relayWiFiPassword = cfg.wifiPassword;
    relayHostOverride = cfg.relayHost;
    relayPortOverride = cfg.relayPort;
    relayTLSOverride  = cfg.relayTLS ? 1 : 0;
    relayTokenOverride = cfg.deviceToken;
    if (cfg.deviceId != nullptr && cfg.deviceId[0] != '\0') {
      strlcpy(relayDeviceId, cfg.deviceId, sizeof(relayDeviceId));
    } else {
      relayDeviceId[0] = '\0'; // derived from the MAC below
    }

    WiFi.mode(WIFI_STA);
    WiFi.begin(relayWiFiSSID, relayWiFiPassword);
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
      delay(400);
      Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[relay] WiFi failed — check the credentials in your sketch");
      return false;
    }
    Serial.printf("[relay] WiFi OK, ip=%s\n", WiFi.localIP().toString().c_str());
    if (relayDeviceId[0] == '\0') {
      // No id given: derive one from the MAC so two boards built from the same
      // sketch never collide on the hub (a collision would have them evicting
      // each other, since re-registration supersedes the incumbent).
      char suffix[7];
      relayMacSuffix(suffix, sizeof(suffix));
      snprintf(relayDeviceId, sizeof(relayDeviceId), "companion-%s", suffix);
      Serial.printf("[relay] device id (from MAC): %s\n", relayDeviceId);
    }

    RelayLinkConfig link = {relayLibraryVersion, relayNeverPushing, relayNoText, relayLibraryFrame};
    relayBegin(link);
    return true;
  }

  // loop must be called from the sketch's loop(): it polls the socket, runs the
  // zombie-link watchdog, and re-dials when the link drops.
  void loop() { relayLinkLoop(); }
};

// CompanionRelay is the singleton sketches use.
CompanionRelayAPI CompanionRelay;
