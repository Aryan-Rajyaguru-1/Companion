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
 *   3. Board dials ws://<hub>/device?token=X, sends device_hello.
 *   4. Agent pushes ANY image (even this same sketch) via PushDevice.
 *   5. Board ACKs bare counts + bare OK, verifies MD5, prints verdict.
 *
 * Edit RELAY_HOST / WIFI_* / tokens before flashing for a given run.
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Update.h>
#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <Preferences.h>
#include <esp_system.h>

using namespace websockets;

// ── Run-local config ─────────────────────────────────────────────────
// Real credentials live in config.local.h (git-ignored via skip-worktree,
// same pattern as the esp32_bridge sketch). The defaults below are inert
// placeholders so the sketch still compiles without the local file.
#if __has_include("config.local.h")
  #include "config.local.h"
#endif

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
  #define DEVICE_ID     "esp32-bridge-01"   // example id — override in config.local.h
#endif
#ifndef RELAY_TLS
  #define RELAY_TLS     false  // true → wss:// (Cloudflare tunnel, port 443)
#endif

static WebsocketsClient ws;
static bool pushActive = false;
static size_t imgSize = 0;
static char deviceSecret[33] = {0}; // per-board identity, NVS-provisioned once

// loadOrCreateDeviceSecret: first boot generates 16 random bytes via the
// hardware RNG, stores them in NVS, and prints them to Serial ONCE (copy it
// into `fleet register --secret` / COMPANION_RELAY_DEVICE_SECRET). Later
// boots read the same value back silently.
static void loadOrCreateDeviceSecret() {
  Preferences prefs;
  prefs.begin("relay", true); // read-only first
  String saved = prefs.getString("secret", "");
  prefs.end();
  if (saved.length() >= 16) {
    strlcpy(deviceSecret, saved.c_str(), sizeof(deviceSecret));
    // Hardware-test sketch: always report the stored secret so it can be
    // registered without an NVS-erase/re-provision cycle. (A production
    // build would print it on first boot only.)
    Serial.printf("[relay] device secret (stored): %s\n", deviceSecret);
    return;
  }
  uint8_t raw[16];
  for (int i = 0; i < 16; i += 4) {
    uint32_t r = esp_random();
    memcpy(raw + i, &r, 4);
  }
  const char *hexd = "0123456789abcdef";
  for (int i = 0; i < 16; i++) {
    deviceSecret[2 * i] = hexd[(raw[i] >> 4) & 0xF];
    deviceSecret[2 * i + 1] = hexd[raw[i] & 0xF];
  }
  deviceSecret[32] = 0;
  prefs.begin("relay", false);
  prefs.putString("secret", deviceSecret);
  prefs.end();
  Serial.println("[relay] *** FIRST BOOT: device secret provisioned ***");
  Serial.printf("[relay] *** SECRET: %s ***\n", deviceSecret);
  Serial.println("[relay] *** copy it now: fleet register --secret-stdin / COMPANION_RELAY_DEVICE_SECRET ***");
}
static char imgMD5[33] = {0};
static size_t written = 0;
static bool headerSeen = false;
static void sendText(const String &s) { ws.send(s); }

static bool wsConnected = false;      // link state, tracked via onEvent
static unsigned long lastDialAttempt = 0;

// onEvt tracks link state so loop() can re-dial after a drop.
static void onEvt(WebsocketsEvent e, String data) {
  (void)data;
  switch (e) {
    case WebsocketsEvent::ConnectionOpened:
      wsConnected = true;
      Serial.println("[relay] link open");
      break;
    case WebsocketsEvent::ConnectionClosed:
      wsConnected = false;
      Serial.println("[relay] link closed — will re-dial");
      break;
    default:
      break;
  }
}

// dialRelay opens the relay link and sends device_hello (carrying the secret).
// Called from setup() and again from loop() whenever the link drops, so a
// tunnel hiccup or WiFi blip self-heals instead of leaving the board offline
// until someone power-cycles it.
static bool dialRelay() {
  lastDialAttempt = millis();
  String url = String(RELAY_TLS ? "wss://" : "ws://") + RELAY_HOST + ":" +
               String(RELAY_PORT) + "/device?token=" + DEVICE_TOKEN;
  Serial.printf("[relay] dialing %s ...\n", url.c_str());
  if (!ws.connect(url)) {
    Serial.println("[relay] ws connect FAILED — retrying in 5s");
    return false;
  }
  StaticJsonDocument<256> hello;
  hello["kind"] = "device_hello";
  hello["id"] = DEVICE_ID;
  hello["version"] = "1.0.3-batch";
  hello["secret"] = deviceSecret;
  // Negotiated data-frame size (KiB): the hub relays this to the agent in
  // push_ack, which then sends 8 KiB frames instead of the legacy 1 KiB ones.
  // The relay path is strict stop-and-wait (one bare ACK per frame), so this
  // is purely the chunk÷RTT lever — an 8 KiB frame turns a ~15 min tunnel
  // push into ~2 min. This board accepts 8 KiB in one onMessage callback
  // (Update.write handles arbitrary sizes; ArduinoWebsockets has no max
  // frame size compiled in).
  hello["frame_kb"] = 8;
  String out; serializeJson(hello, out);
  sendText(out);
  wsConnected = true;
  Serial.printf("[relay] registered as %s — waiting for pushes\n", DEVICE_ID);
  return true;
}


static void sendStatus(const char *msg) {
  StaticJsonDocument<192> d;
  d["kind"] = "status";
  d["msg"] = msg;
  String out; serializeJson(d, out);
  sendText(out);
}

// onMessage: control frames (push_start JSON) AND firmware frames both land
// here — the ArduinoWebsockets lib hands us text vs binary distinctly.
static void onMsg(WebsocketsMessage msg) {
  if (msg.isText()) {
    String t = msg.data();
    if (t.indexOf("push_start") >= 0) {
      StaticJsonDocument<256> d;
      if (deserializeJson(d, t)) { sendStatus("bad push_start"); return; }
      imgSize = (size_t)(long)d["size"];
      strlcpy(imgMD5, (const char *)d["md5"], sizeof(imgMD5));
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
        ws.sendBinary("ERROR begin failed",
                      strlen("ERROR begin failed"));
        return;
      }
      Update.setMD5(imgMD5);
      pushActive = true; written = 0; headerSeen = false;
      sendStatus("update begun");
    }
    return;
  }
  // ── Binary frame: raw firmware bytes (maybe header-prefixed first) ──
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
    ws.sendBinary("ERROR flash failed", strlen("ERROR flash failed"));
    pushActive = false;
    return;
  }
  written += w;
  // BARE decimal ACK — no newline, exactly like ArduinoOTA on LAN.
  char ack[16];
  snprintf(ack, sizeof(ack), "%u", (unsigned)w);
  ws.sendBinary(ack, strlen(ack));

  if (written >= imgSize) {
    if (Update.end(true)) {
      Serial.printf("[relay] Update.end OK — %u bytes, rebooting\n",
                    (unsigned)written);
      ws.sendBinary("OK", 2);
      // push_done (text control): explicit end-of-push so the hub clears the
      // pairing — the board stays connected and is immediately pushable again.
      StaticJsonDocument<64> done;
      done["kind"] = "push_done";
      String doneOut; serializeJson(done, doneOut);
      sendText(doneOut);
      // Now boot the freshly written image. Give the frames a moment to
      // flush through the relay before the reset drops the socket.
      Serial.println("[relay] rebooting into the new image");
      ws.poll();
      delay(400);
      ESP.restart();
    } else {
      Serial.printf("[relay] Update.end FAILED: %s\n",
                    Update.errorString());
      String e = String("ERROR ") + Update.errorString();
      ws.sendBinary(e.c_str(), e.length());
    }
    pushActive = false;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);   // heartbeat: driven from loop()
  digitalWrite(LED_BUILTIN, LOW);
  delay(400);
  Serial.println();
  Serial.println("========================================");
  Serial.println("COMPANION_RELAY_DEVICE_TEST");
  Serial.println("========================================");
  loadOrCreateDeviceSecret();

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

  ws.onMessage(onMsg);
  ws.onEvent(onEvt);
  dialRelay();
}

void loop() {
  ws.poll();

  // Self-healing link: re-dial when the connection drops (tunnel restart,
  // WiFi blip, hub restart) instead of staying offline until a power cycle.
  if (!wsConnected && millis() - lastDialAttempt > 5000) {
    if (WiFi.status() == WL_CONNECTED) {
      dialRelay();
    }
  }

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
                  WiFi.localIP().toString().c_str(), (int)wsConnected,
                  (int)pushActive, (unsigned)written, (unsigned)imgSize);
  }
}
