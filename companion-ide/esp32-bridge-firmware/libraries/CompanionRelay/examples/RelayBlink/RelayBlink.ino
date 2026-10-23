// RelayBlink — a link demonstration, NOT an OTA receiver.
//
// Build it with Companion CLI (or any Arduino-compatible toolchain). It dials
// the hub outbound and prints any binary frame it receives, but it does not
// call Update/ACK, so `relay push` cannot flash it. See RelayDevice.ino for the
// complete ArduinoOTA-compatible receiver.
#include <Arduino.h>
#include <CompanionRelay.h>

// Some esp32 core variants do not define LED_BUILTIN; the DevKit v1's
// on-board LED is on GPIO 2.
#ifndef LED_BUILTIN
  #define LED_BUILTIN 2
#endif

// The hub validated the sender with the board's per-device secret before any
// bytes arrived, but this library only delivers frames: it has not begun an
// update or verified the image. A real receiver hands these bytes to Update and
// ACKs them; see RelayDevice.ino.
static void onRelayFrame(uint8_t *data, size_t n) {
  Serial.printf("[relay] received %u binary bytes\n", (unsigned)n);
  (void)data;
}

static void onRelayText(const String &text) {
  Serial.printf("[relay] text: %s\n", text.c_str());
}

static void onRelayCommand(const char *kind) {
  Serial.printf("[relay] command: %s\n", kind);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(LED_BUILTIN, OUTPUT);

  CompanionRelayConfig cfg;
  cfg.wifiSSID     = "YOUR_WIFI_SSID";
  cfg.wifiPassword = "YOUR_WIFI_PASSWORD";
  cfg.relayHost    = "ota.example.com";
  cfg.relayPort    = 443;
  cfg.relayTLS     = true;
  // REQUIRED for wss://: the PEM trust anchor for the hub's certificate.
  // TLS is fail-closed — leaving this as a placeholder makes begin() refuse
  // rather than silently call setInsecure().
  cfg.caCert       = "YOUR_RELAY_CA_CERT";
  cfg.deviceToken  = "YOUR_DEVICE_TOKEN";
  cfg.deviceId     = "";  // empty -> MAC-derived unique id
  cfg.onFrame      = onRelayFrame;
  cfg.onText       = onRelayText;   // full control frame, including push_start
  cfg.onCommand    = onRelayCommand;
  CompanionRelay.begin(cfg);

  Serial.println("[relay] blink running — link demo only (no OTA receiver)");
}

void loop() {
  CompanionRelay.loop();
  static unsigned long last = 0;
  if (millis() - last > 500) {
    last = millis();
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  }
}
