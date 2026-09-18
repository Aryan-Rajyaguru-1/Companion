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

using namespace websockets;

// ── Run-local config: edit per test run ──────────────────────────────
#define WIFI_SSID     "YOUR_WIFI_SSID"
#define WIFI_PASS     "YOUR_WIFI_PASSWORD"
#define RELAY_HOST    "YOUR_HUB_LAN_IP"  // laptop LAN IP running the hub
#define RELAY_PORT    8931
#define DEVICE_TOKEN  "dev-tok"
#define DEVICE_ID     "esp32-remotetest-01"

static WebsocketsClient ws;
static bool pushActive = false;
static size_t imgSize = 0;
static char imgMD5[33] = {0};
static size_t written = 0;
static bool headerSeen = false;
static uint8_t chunkBuf[1024];
static size_t chunkLen = 0;

static void sendText(const String &s) { ws.send(s); }

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
      if (!Update.begin(imgSize)) {
        Serial.printf("[relay] Update.begin FAILED: %s\n",
                      Update.errorString());
        ws.sendBinary("ERROR begin failed",
                      strlen("ERROR begin failed"));
        return;
      }
      Update.setMD5(imgMD5);
      pushActive = true; written = 0; headerSeen = false; chunkLen = 0;
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
  size_t w = Update.write(p, n);
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

  ws.onMessage(onMsg);
  String url = String("ws://") + RELAY_HOST + ":" + RELAY_PORT +
               "/device?token=" + DEVICE_TOKEN;
  Serial.printf("[relay] dialing %s ...\n", url.c_str());
  if (!ws.connect(url)) {
    Serial.println("[relay] ws connect FAILED — is the hub running?");
    return;
  }
  StaticJsonDocument<192> hello;
  hello["kind"] = "device_hello";
  hello["id"] = DEVICE_ID;
  hello["version"] = "1.0.0-test";
  String out; serializeJson(hello, out);
  sendText(out);
  Serial.printf("[relay] registered as %s — waiting for pushes\n", DEVICE_ID);
}

void loop() {
  ws.poll();
  static unsigned long last = 0;
  if (millis() - last > 5000) {
    last = millis();
    Serial.printf("[relay] alive ip=%s push=%d written=%u/%u\n",
                  WiFi.localIP().toString().c_str(), (int)pushActive,
                  (unsigned)written, (unsigned)imgSize);
  }
}
