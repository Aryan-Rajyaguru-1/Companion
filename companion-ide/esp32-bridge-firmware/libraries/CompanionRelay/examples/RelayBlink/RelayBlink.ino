// RelayBlink — a sketch that can be re-flashed from anywhere on the internet.
//
// Build it however you like (Companion CLI, arduino-cli, Arduino IDE), then:
//
//   companion relay push --hub wss://ota.example.com \
//     --device esp32-node-01 firmware.bin
//
// The board dials the hub outbound, so no inbound port is needed here and the
// same command works from a laptop that is nowhere near the board.
#include <Arduino.h>
#include <CompanionRelay.h>

// Some esp32 core variants do not define LED_BUILTIN; the DevKit v1's
// on-board LED is on GPIO 2.
#ifndef LED_BUILTIN
  #define LED_BUILTIN 2
#endif

// The hub validated this push with the board's per-device secret before any
// bytes arrived; the library has already checked the framing and the image MD5.
static void onRelayFrame(uint8_t *data, size_t n) {
  Serial.printf("[relay] received %u bytes of firmware\n", (unsigned)n);
  // A real sketch would hand these to Update.begin()/Update.write() — see
  // RelayDevice.ino in companion-ide/esp32-bridge-firmware for a complete
  // OTA state machine. This example only proves the link works.
  (void)data;
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
  cfg.deviceToken  = "YOUR_DEVICE_TOKEN";
  cfg.deviceId     = "esp32-node-01";  // unique per board
  cfg.onFrame      = onRelayFrame;
  cfg.onCommand    = onRelayCommand;
  CompanionRelay.begin(cfg);

  Serial.println("[relay] blink running — this board is now remote-flashable");
}

void loop() {
  CompanionRelay.loop();
  static unsigned long last = 0;
  if (millis() - last > 500) {
    last = millis();
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  }
}
