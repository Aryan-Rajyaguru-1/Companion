/*
 * RelayDevice — ESP32 firmware speaking the Companion relay device protocol.
 *
 * Purpose: prove the ENTIRE remote-OTA chain on real hardware:
 *   ESP32 (this sketch) ──ws──► relay hub (Jetson/laptop) ◄──ws── agent (PushDevice)
 * with the firmware bytes flowing through the hub to this board, which
 * writes them via Update exactly like a LAN ArduinoOTA push.
 *
 * HARDWARE TEST ONLY — not part of any product sketch. Flow:
 *   1. Board joins the lab WiFi (STA) so it can reach the hub on the LAN.
 *   2. Hub runs on this laptop: `relay-hub -listen :8931 -devices-token X`
 *      (or the httptest hub; same protocol).
 *   3. Board dials ws://<hub>/device (Authorization: Bearer X), sends device_hello.
 *   4. Agent pushes ANY image (even this same sketch) via PushDevice.
 *   5. Board ACKs bare counts + bare OK, verifies the ArduinoOTA-compatible
 *      MD5 (a corruption check, not a signature), prints verdict.
 *
 * Edit RELAY_HOST / WIFI_* / tokens before flashing for a given run.
 * The WiFi/dial/heartbeat/reconnect block lives ONCE, in
 * ../shared/relay_link.h — this sketch only supplies the OTA behaviour.
 */

#include <Arduino.h>
#include <ctype.h>
#include <ArduinoJson.h>
#include <Update.h>
#include <WiFi.h>
#include <ArduinoOTA.h>

// ── Run-local config ─────────────────────────────────────────────────
// Real credentials live in config.local.h (git-ignored, same pattern as the
// esp32_bridge sketch). The defaults below are inert placeholders so the
// sketch still compiles without the local file. They MUST precede the shared
// header include: relayDial reads RELAY_HOST/PORT/TLS/DEVICE_TOKEN.
#if __has_include("config.local.h")
  #include "config.local.h"
#endif

// RELAY_LAN_OTA adds a LAN ArduinoOTA service alongside the relay link — a
// RECOVERY PATH, and the fix for this board's single point of failure. The
// relay is how firmware arrives, so if the hub is down, the tunnel breaks, or
// the board is mis-provisioned, the only way back was a USB cable. With this
// on, the same board can be re-flashed over WiFi with
//   companion ota upload <board-ip> --ota-mode local
// Default OFF: it is one more network service (ArduinoOTA has no per-device
// secret of its own), and it refuses to start without a configured password.
#ifndef RELAY_LAN_OTA
  #define RELAY_LAN_OTA 0
#endif
// LAN OTA is fail-closed: enabling it without a real password disables the
// service instead of starting an unauthenticated reflash endpoint.
#ifndef RELAY_LAN_OTA_PASSWORD
  #define RELAY_LAN_OTA_PASSWORD ""
#endif
static bool lanOtaPasswordUsable(const char *v) {
  if (v == nullptr || strlen(v) < 8) return false;
  if (strncmp(v, "YOUR_", 5) == 0) return false;
  if (strncmp(v, "CHANGE_ME", 9) == 0) return false;
  if (strcmp(v, "flashme!") == 0) return false;
  return true;
}
static bool lanOtaStarted = false;

// Generic esp32 core variants don't define LED_BUILTIN; the DevKit v1's
// on-board LED sits on GPIO 2 (active-high).
#ifndef LED_BUILTIN
  #define LED_BUILTIN 2
#endif

#ifndef WIFI_SSID
  #define WIFI_SSID     "YOUR_WIFI_SSID"
#endif
#ifndef WIFI_PASS
  #define WIFI_PASS     "YOUR_WIFI_PASSWORD"
#endif
#ifndef RELAY_HOST
  #define RELAY_HOST    "YOUR_HUB_LAN_IP"  // host running `companion relay hub`
#endif
#ifndef RELAY_PORT
  #define RELAY_PORT    8931
#endif
#ifndef DEVICE_TOKEN
  #define DEVICE_TOKEN  "YOUR_DEVICE_TOKEN"  // COMPANION_RELAY_DEVICES_TOKEN on the hub
#endif
#ifndef DEVICE_ID
  #define DEVICE_ID     "esp32-bridge-01"   // placeholder; setup() derives a MAC-suffixed id
#endif
#ifndef RELAY_TLS
  #define RELAY_TLS     false  // true → wss:// (Cloudflare tunnel, port 443)
#endif

// The library includes stay in the sketch: the builder discovers libraries by
// scanning the sketch's OWN sources, and headers under ../shared/ are outside
// that scan (the shared header includes them too; guards make it harmless).
#include <ArduinoWebsockets.h>
#include <Preferences.h>

// Explicit prototypes: Arduino's auto-generator emits prototypes BEFORE any
// include, where WebsocketsMessage isn't declared yet — declaring them here
// (post-include) makes the generator skip them.
// (The handlers are static: Arduino's prototype generator skips static
//  functions, so no prototype is emitted before the includes where
//  WebsocketsMessage would be undeclared — the old onMsg relied on this.)

// The shared dial-out link: WS object, NVS secret, device_hello, the
// zombie-link watchdog (ping/pong) and the re-dial loop — ONE copy, shared
// with esp32_bridge.
#include "../shared/relay_link.h"

// ── OTA state ────────────────────────────────────────────────────────
static bool pushActive = false;
static size_t imgSize = 0;
static char imgMD5[33] = {0};
static size_t written = 0;
static bool headerSeen = false;

// ── Relay link callbacks (non-static: Arduino generates matching
//    prototypes; the config below needs them declared first) ──────────
static const char *fwVersion() { return "1.0.3-batch"; }
static bool relayPushActiveFn() { return pushActive; }

// onRelayText: control frames (push_start JSON). The heartbeat pong is
// consumed inside relay_link.h before this runs.
static bool isMD5Hex(const char *s) {
  if (s == nullptr || strlen(s) != 32) return false;
  for (size_t i = 0; i < 32; i++) {
    if (!isxdigit((unsigned char)s[i])) return false;
  }
  return true;
}

static void onRelayText(const String &t) {
  StaticJsonDocument<256> d;
  if (deserializeJson(d, t)) return;
  const char *kind = d["kind"] | "";
  if (strcmp(kind, "push_start") != 0) return;

  long announced = d["size"] | 0L;
  // A push_start with no md5 (or a non-string value) used to go straight
  // into strlcpy as NULL, which crashes the board — so one malformed frame
  // from any paired agent killed the link until a manual reflash. Treat it
  // as the protocol error it is. Validate the digest's exact shape too:
  // strlcpy() would silently truncate a malformed value and Update.setMD5()
  // would then compare against a digest that can never match.
  const char *md5 = d["md5"] | "";
  if (announced <= 0) {
    Serial.println("[relay] push_start with invalid size — rejecting");
    relaySendStatus("push_start with invalid size");
    return;
  }
  if (!isMD5Hex(md5)) {
    Serial.println("[relay] push_start has invalid md5 — rejecting");
    relaySendStatus("push_start has invalid md5");
    return;
  }
  imgSize = (size_t)announced;
  strlcpy(imgMD5, md5, sizeof(imgMD5));
  Serial.printf("[relay] push_start size=%u md5=%s\n",
                (unsigned)imgSize, imgMD5);
  // A push killed mid-stream (agent deadline, tunnel drop) leaves the
  // updater holding a half-open session; Update.begin() then refuses
  // every future push with "begin failed". Abort any stale session
  // before starting fresh — self-heals without a power cycle.
  if (pushActive || (!Update.isFinished() && Update.size() > 0)) {
    Update.abort();
    pushActive = false;
    Serial.println("[relay] cleared stale OTA session");
  }
  if (!Update.begin(imgSize)) {
    Serial.printf("[relay] Update.begin FAILED: %s\n",
                  Update.errorString());
    relaySendBinary("ERROR begin failed", strlen("ERROR begin failed"));
    return;
  }
  Update.setMD5(imgMD5);
  pushActive = true; written = 0; headerSeen = false;
  relaySendStatus("update begun");
}

// onRelayBinary: raw firmware bytes (maybe header-prefixed first). Strict
// stop-and-wait: one bare decimal ACK per frame, then the final bare "OK"
// only after Update.end() verifies the full-image MD5.
static void onRelayBinary(WebsocketsMessage &msg) {
  if (!pushActive) return;
  const uint8_t *p = (const uint8_t *)msg.c_str();
  size_t n = msg.length();
  // First frame carries the "<size> <md5>\n" ASCII header PushDevice sends.
  if (!headerSeen) {
    const uint8_t *nl = (const uint8_t *)memchr(p, '\n', n > 80 ? 80 : n);
    if (nl) {
      size_t skip = (nl - p) + 1;
      p += skip; n -= skip;
    }
    headerSeen = true;
  }
  if (n == 0) return;
  // Core 3.3.11's Update API takes a non-const buffer; it only reads it.
  size_t w = Update.write(const_cast<uint8_t *>(p), n);
  if (w != n) {
    Serial.printf("[relay] Update.write FAILED (%u/%u): %s\n",
                  (unsigned)w, (unsigned)n, Update.errorString());
    relaySendBinary("ERROR flash failed", strlen("ERROR flash failed"));
    pushActive = false;
    return;
  }
  written += w;
  // BARE decimal ACK — no newline, exactly like ArduinoOTA on LAN.
  char ack[16];
  snprintf(ack, sizeof(ack), "%u", (unsigned)w);
  relaySendBinary(ack, strlen(ack));

  if (written >= imgSize) {
    if (Update.end(true)) {
      Serial.printf("[relay] Update.end OK — %u bytes, rebooting\n",
                    (unsigned)written);
      relaySendBinary("OK", 2);
      // push_done (text control): explicit end-of-push so the hub clears the
      // pairing — the board stays connected and is immediately pushable again.
      StaticJsonDocument<64> done;
      done["kind"] = "push_done";
      String doneOut; serializeJson(done, doneOut);
      relaySendText(doneOut);
      // Now boot the freshly written image. Give the frames a moment to
      // flush through the relay before the reset drops the socket.
      Serial.println("[relay] rebooting into the new image");
      relayWs.poll();
      delay(400);
      ESP.restart();
    } else {
      Serial.printf("[relay] Update.end FAILED: %s\n",
                    Update.errorString());
      String e = String("ERROR ") + Update.errorString();
      relaySendBinary(e.c_str(), e.length());
    }
    pushActive = false;
  }
}

// ── Link configuration ───────────────────────────────────────────────
static const RelayLinkConfig relayLink = {
  fwVersion,         // version reported in device_hello
  relayPushActiveFn, // pushActive — the watchdog stands down mid-push
  onRelayText,       // text/control frames
  onRelayBinary,     // binary frames
};

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);   // heartbeat: driven from loop()
  digitalWrite(LED_BUILTIN, LOW);
  delay(400);
  Serial.println();
  Serial.println("========================================");
  Serial.println("COMPANION_RELAY_DEVICE_TEST");
  Serial.println("========================================");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("[relay] joining %s", WIFI_SSID);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(400); Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[relay] WiFi FAILED — check WIFI_SSID/WIFI_PASS");
    return;
  }
  Serial.printf("[relay] WiFi OK, ip=%s rssi=%d\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());

#if RELAY_LAN_OTA
  // Recovery path. Runs beside the relay, never instead of it: a board can be
  // updated over the LAN while the hub is unreachable, and over the relay
  // while this is off. The relay link still comes up below either way.
  if (!lanOtaPasswordUsable(RELAY_LAN_OTA_PASSWORD)) {
    Serial.println("[lanota] DISABLED: set RELAY_LAN_OTA_PASSWORD (8+ chars) in config.local.h");
  } else {
    char suffix[7];
    relayMacSuffix(suffix, sizeof(suffix));
    char host[40];
    snprintf(host, sizeof(host), "companion-%s", suffix);
    ArduinoOTA.setHostname(host);
    ArduinoOTA.setPassword(RELAY_LAN_OTA_PASSWORD);
    ArduinoOTA.onStart([]() { Serial.println("[lanota] update starting — relay link unaffected"); });
    ArduinoOTA.onProgress([](unsigned int done, unsigned int total) {
      static int lastPct = -1;
      int pct = (int)(done * 100 / total);
      if (pct != lastPct && pct % 25 == 0) {
        lastPct = pct;
        Serial.printf("[lanota] %d%%\n", pct);
      }
    });
    ArduinoOTA.onEnd([]() { Serial.println("[lanota] update done — rebooting"); });
    ArduinoOTA.onError([](ota_error_t e) { Serial.printf("[lanota] error %u\n", e); });
    ArduinoOTA.begin();
    lanOtaStarted = true;
    Serial.printf("[lanota] LAN recovery service UP (hostname %s, port 3232)\n", host);
    Serial.println("[lanota] recover with: companion ota upload <ip> --ota-mode local");
  }
#endif

  // A fixed DEVICE_ID from config.local.h always wins. The example default is
  // only a placeholder: replace it with a MAC-derived suffix so two boards
  // copied from the same example cannot collide (and evict each other) on the
  // hub.
  if (strcmp(DEVICE_ID, "esp32-bridge-01") == 0) {
    char suffix[7];
    relayMacSuffix(suffix, sizeof(suffix));
    snprintf(relayDeviceId, sizeof(relayDeviceId), "relay-%s", suffix);
  } else {
    strlcpy(relayDeviceId, DEVICE_ID, sizeof(relayDeviceId));
  }

  relayBegin(relayLink);   // secret + callbacks + dial
}

void loop() {
  relayLinkLoop();   // poll + zombie-watchdog + re-dial (shared)
#if RELAY_LAN_OTA
  if (lanOtaStarted) ArduinoOTA.handle();   // LAN recovery path (RELAY_LAN_OTA)
#endif

  // Built-in LED heartbeat, driven from the alive-logger tick: slow 2 Hz
  // blink while idle, fast 8 Hz while a push is streaming.
  static unsigned long last = 0;
  static bool ledState = false;
  unsigned long period = pushActive ? 125 : 500;
  if (millis() - last > period) {
    last = millis();
    ledState = !ledState;
    digitalWrite(LED_BUILTIN, ledState ? HIGH : LOW);
    Serial.printf("[relay] alive ip=%s link=%d push=%d written=%u/%u\n",
                  WiFi.localIP().toString().c_str(), (int)relayWsConnected,
                  (int)pushActive, (unsigned)written, (unsigned)imgSize);
  }
}
