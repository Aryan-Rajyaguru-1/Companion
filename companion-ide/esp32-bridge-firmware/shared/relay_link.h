// relay_link.h — the shared dial-out relay link for Companion ESP32 sketches.
//
// ONE copy of the WiFi/dial/hello/heartbeat/reconnect block, included by both
// sketches (RelayDevice and esp32_bridge). Factored deliberately: two sketches
// claiming the same contract by hand is the exact "drift apart" shape that
// bit the --ota-mode default.
//
// The sketch configures it with a RelayLinkConfig (callback pointers, so no
// name-based prototype conflicts with Arduino's auto-generated prototypes):
//
//   version    — the firmware version string reported in device_hello
//   onText     — a TEXT frame from the hub (control/protocol; the heartbeat
//                pong is consumed internally first)
//   onBinary   — a BINARY frame from the hub (OTA bytes / UART data)
//
// Usage:
//   #include "../shared/relay_link.h"        (resolves via the sketch's -I)
//   static const RelayLinkConfig relayCfg = {...};
//   setup():  relayBegin(relayCfg);
//   loop():   relayLinkLoop();
//
// The board dials the hub OUTBOUND (wss://host:port/device?token=...), so no
// inbound ports are needed anywhere, and the zombie-link watchdog (ping/pong,
// answered by the hub) re-dials when a connection dies without a close frame.

#pragma once

#include <Arduino.h>
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
  String url = String(RELAY_TLS ? "wss://" : "ws://") + RELAY_HOST + ":" +
               String(RELAY_PORT) + "/device?token=" + DEVICE_TOKEN;
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