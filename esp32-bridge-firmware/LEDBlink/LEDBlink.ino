/*
 * LEDBlink — Companion OTA verification sketch.
 *
 * Blinks the built-in LED (GPIO 2 on most ESP32 dev boards) and prints a
 * heartbeat over USB serial, so an OTA update can be confirmed two ways:
 * visually (LED) and by watching the counter roll over serial.
 */

#define LED_PIN 2

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("========================================");
  Serial.println("COMPANION_OTA_LED_OK");
  Serial.println("========================================");
  Serial.printf("chip: %s rev %d, cores %d\n",
                ESP.getChipModel(), ESP.getChipRevision(), ESP.getChipCores());
  Serial.printf("free heap: %u bytes\n", (unsigned)ESP.getFreeHeap());
  Serial.println("Blinking built-in LED on GPIO 2...");
}

void loop() {
  static uint32_t n = 0;
  digitalWrite(LED_PIN, HIGH);
  Serial.printf("[led] ON  #%lu  heap=%u\n", (unsigned long)++n,
                (unsigned)ESP.getFreeHeap());
  delay(500);
  digitalWrite(LED_PIN, LOW);
  Serial.printf("[led] OFF #%lu\n", (unsigned long)n);
  delay(500);
}