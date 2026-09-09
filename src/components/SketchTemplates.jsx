/**
 * SketchTemplates.jsx
 * Template picker modal — lets users start from a working example
 * rather than a blank sketch.
 *
 * Pattern from arduino-ide-main's file-new.ts template selection.
 */

import { useState } from 'react';
import './SketchTemplates.css';

const TEMPLATES = [
  {
    id: 'blink',
    label: 'Blink',
    description: 'Blink the built-in LED every second.',
    tags: ['beginner', 'gpio'],
    fqbn: null, // any board
    code: `/*
 * Blink — blink the built-in LED.
 * Works on any Arduino-compatible board. Boards without a defined
 * LED_BUILTIN (e.g. generic ESP32 Dev Modules) fall back to GPIO 2,
 * which most dev boards wire to an onboard LED.
 */

#ifdef LED_BUILTIN
  #define BLINK_PIN LED_BUILTIN
#else
  #define BLINK_PIN 2   // generic fallback: most ESP32 dev boards use GPIO 2
#endif

void setup() {
  pinMode(BLINK_PIN, OUTPUT);
  Serial.begin(115200);
  Serial.println("Blink started");
}

void loop() {
  digitalWrite(BLINK_PIN, HIGH);  // LED on
  delay(1000);
  digitalWrite(BLINK_PIN, LOW);   // LED off
  delay(1000);
}
`,
  },
  {
    id: 'serial-hello',
    label: 'Serial Hello',
    description: 'Print "Hello, World!" over Serial at 115200 baud.',
    tags: ['beginner', 'serial'],
    fqbn: null,
    code: `/*
 * Serial Hello — send text over Serial Monitor.
 * Open Serial Monitor at 115200 baud to see output.
 */

void setup() {
  Serial.begin(115200);
  while (!Serial) {}   // wait for Serial on native USB boards
  Serial.println("Hello from Companion IDE!");
}

void loop() {
  static unsigned long last = 0;
  if (millis() - last >= 2000) {
    last = millis();
    Serial.print("Uptime: ");
    Serial.print(millis() / 1000);
    Serial.println("s");
  }
}
`,
  },
  {
    id: 'wifi-connect',
    label: 'WiFi Connect',
    description: 'Connect to a WiFi network and print the IP address.',
    tags: ['networking', 'esp32', 'esp8266'],
    fqbn: 'esp32:esp32:esp32',
    code: `/*
 * WiFi Connect — connect to WiFi and print IP.
 * Requires: WiFi library (ESP32/ESP8266 core)
 */

#include <WiFi.h>   // ESP32 — use <ESP8266WiFi.h> for ESP8266

const char* SSID     = "your-network-name";
const char* PASSWORD = "your-password";

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.print("Connecting to ");
  Serial.print(SSID);

  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("Connected! IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // Your connected logic here
  delay(10000);
}
`,
  },
  {
    id: 'web-server',
    label: 'Web Server',
    description: 'Serve a simple web page over WiFi (ESP32/ESP8266).',
    tags: ['networking', 'esp32'],
    fqbn: 'esp32:esp32:esp32',
    code: `/*
 * Web Server — serve a simple HTML page over WiFi.
 * Visit the IP address shown in Serial Monitor.
 */

#include <WiFi.h>
#include <WebServer.h>

const char* SSID     = "your-network-name";
const char* PASSWORD = "your-password";

WebServer server(80);

void handleRoot() {
  server.send(200, "text/html",
    "<h1>Hello from Companion IDE!</h1>"
    "<p>Board is alive and serving.</p>");
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }

  Serial.print("\\nServer at http://");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.begin();
}

void loop() {
  server.handleClient();
}
`,
  },
  {
    id: 'mqtt-client',
    label: 'MQTT Client',
    description: 'Connect to an MQTT broker and publish/subscribe.',
    tags: ['iot', 'esp32', 'mqtt'],
    fqbn: 'esp32:esp32:esp32',
    code: `/*
 * MQTT Client — publish and subscribe to topics.
 * Requires: PubSubClient library
 */

#include <WiFi.h>
#include <PubSubClient.h>

const char* SSID        = "your-ssid";
const char* PASSWORD    = "your-password";
const char* MQTT_SERVER = "192.168.1.100";  // broker IP
const char* TOPIC_PUB   = "companion/status";
const char* TOPIC_SUB   = "companion/command";

WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);

void onMessage(char* topic, byte* payload, unsigned int length) {
  String msg = String((char*)payload).substring(0, length);
  Serial.print("Received [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(msg);
}

void reconnect() {
  while (!mqtt.connected()) {
    Serial.print("MQTT connect...");
    if (mqtt.connect("companion-device")) {
      mqtt.subscribe(TOPIC_SUB);
      Serial.println("ok");
    } else {
      Serial.print("failed (");
      Serial.print(mqtt.state());
      Serial.println("), retry in 5s");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  Serial.println("WiFi OK");

  mqtt.setServer(MQTT_SERVER, 1883);
  mqtt.setCallback(onMessage);
}

void loop() {
  if (!mqtt.connected()) reconnect();
  mqtt.loop();

  static unsigned long last = 0;
  if (millis() - last >= 5000) {
    last = millis();
    mqtt.publish(TOPIC_PUB, "alive");
  }
}
`,
  },
  {
    id: 'ota-update',
    label: 'OTA Update',
    description: 'Enable over-the-air firmware updates via WiFi.',
    tags: ['ota', 'esp32', 'wifi'],
    fqbn: 'esp32:esp32:esp32',
    code: `/*
 * OTA Update — enable firmware updates over WiFi.
 * After upload, use Arduino IDE's "Upload via Network" or
 * companion upload to push new firmware wirelessly.
 */

#include <WiFi.h>
#include <ArduinoOTA.h>

const char* SSID     = "your-ssid";
const char* PASSWORD = "your-password";

void setup() {
  Serial.begin(115200);
  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.print("\\nIP: ");
  Serial.println(WiFi.localIP());

  ArduinoOTA.setHostname("companion-device");
  ArduinoOTA.onStart([]()  { Serial.println("OTA Start"); });
  ArduinoOTA.onEnd([]()    { Serial.println("\\nOTA Done");  });
  ArduinoOTA.onProgress([](unsigned int p, unsigned int t) {
    Serial.printf("Progress: %u%%\\r", (p * 100) / t);
  });
  ArduinoOTA.onError([](ota_error_t e) {
    Serial.printf("OTA Error[%u]\\n", e);
  });
  ArduinoOTA.begin();
  Serial.println("OTA ready");
}

void loop() {
  ArduinoOTA.handle();
  // Your application logic here
}
`,
  },
  {
    id: 'sensor-dht',
    label: 'DHT Sensor',
    description: 'Read temperature and humidity from a DHT11/DHT22.',
    tags: ['sensor', 'beginner'],
    fqbn: null,
    code: `/*
 * DHT Temperature & Humidity Sensor
 * Requires: "DHT sensor library" by Adafruit
 */

#include <DHT.h>

#define DHT_PIN  4       // data pin
#define DHT_TYPE DHT22   // or DHT11

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  dht.begin();
  Serial.println("DHT sensor ready");
}

void loop() {
  delay(2000);  // DHT needs ~2s between readings

  float humidity    = dht.readHumidity();
  float temperature = dht.readTemperature();   // Celsius; use readTemperature(true) for Fahrenheit

  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("Failed to read from DHT sensor!");
    return;
  }

  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.print(" %  Temperature: ");
  Serial.print(temperature);
  Serial.println(" °C");
}
`,
  },
  {
    id: 'neopixel',
    label: 'NeoPixel LEDs',
    description: 'Animate a strip of WS2812B addressable LEDs.',
    tags: ['led', 'beginner'],
    fqbn: null,
    code: `/*
 * NeoPixel LED Strip
 * Requires: "Adafruit NeoPixel" library
 */

#include <Adafruit_NeoPixel.h>

#define LED_PIN   6    // data pin to strip DIN
#define LED_COUNT 12   // number of LEDs

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
  strip.begin();
  strip.show();   // start with all off
  strip.setBrightness(80);
}

void loop() {
  // Cycle hue across all pixels
  for (long hue = 0; hue < 5 * 65536; hue += 256) {
    strip.rainbow(hue);
    strip.show();
    delay(10);
  }
}
`,
  },
];

// ── Tag colours ─────────────────────────────────────────────────────
const TAG_COLORS = {
  beginner:   '#238636',
  networking: '#1f6feb',
  iot:        '#7d4e75',
  esp32:      '#b08800',
  esp8266:    '#b08800',
  sensor:     '#0f4a6e',
  led:        '#6e3040',
  mqtt:       '#6e3040',
  ota:        '#2f5a2f',
  serial:     '#333',
  gpio:       '#333',
  wifi:       '#1f6feb',
};

// ── Component ────────────────────────────────────────────────────────
export default function SketchTemplates({ onSelect, onClose, currentFQBN }) {
  const [search, setSearch]     = useState('');
  const [selected, setSelected] = useState(null);

  const filtered = TEMPLATES.filter(t => {
    const q = search.toLowerCase();
    return (
      t.label.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.tags.some(tag => tag.includes(q))
    );
  });

  const handleOpen = (tpl) => {
    onSelect({ name: `${tpl.id}.ino`, code: tpl.code });
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal templates-modal">
        <div className="modal-header">
          <span className="modal-title"><TemplateIcon /> New from Template</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="templates-search-row">
          <input
            className="templates-search"
            type="search"
            placeholder="Search templates…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoFocus
          />
        </div>

        <div className="templates-body">
          {/* Template list */}
          <div className="templates-list">
            {filtered.length === 0 && (
              <div className="templates-empty">No templates match "{search}"</div>
            )}
            {filtered.map(t => (
              <div
                key={t.id}
                className={`template-card ${selected?.id === t.id ? 'selected' : ''}`}
                onClick={() => setSelected(t)}
                onDoubleClick={() => handleOpen(t)}
              >
                <div className="tc-header">
                  <span className="tc-label">{t.label}</span>
                  {t.fqbn && (
                    <span className="tc-board" title={t.fqbn}>
                      {t.fqbn.split(':').slice(0, 2).join(':')}
                    </span>
                  )}
                </div>
                <div className="tc-desc">{t.description}</div>
                <div className="tc-tags">
                  {t.tags.map(tag => (
                    <span key={tag} className="tc-tag"
                      style={{ background: TAG_COLORS[tag] || '#333' }}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Preview pane */}
          <div className="templates-preview">
            {selected ? (
              <>
                <div className="tp-header">
                  <strong>{selected.label}</strong>
                  <span className="tp-desc">{selected.description}</span>
                </div>
                <pre className="tp-code"><code>{selected.code}</code></pre>
                <div className="tp-actions">
                  <button className="btn btn-primary" onClick={() => handleOpen(selected)}>
                    Open Template
                  </button>
                  <button className="btn" onClick={onClose}>Cancel</button>
                </div>
              </>
            ) : (
              <div className="tp-empty">Select a template to preview</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TemplateIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <path d="M3 9h18M9 21V9"/>
    </svg>
  );
}
