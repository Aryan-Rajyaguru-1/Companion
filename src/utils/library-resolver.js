/**
 * library-resolver.js
 * P1 — Structured error analysis: detects missing libraries from compile errors
 * and prepares install suggestions.
 *
 * Pattern from arduino-ide-main's library service which parses compiler errors
 * to auto-suggest missing libraries rather than just showing raw error text.
 */

// ── Header → Library name mapping ──────────────────────────────────
//
// Maps common Arduino #include headers to the installable library name.
// This is the same pattern used by the Arduino IDE's library resolver.
const HEADER_TO_LIBRARY = {
  // Networking
  'WiFi.h':             'WiFi',
  'WiFiClient.h':       'WiFi',
  'WiFiServer.h':       'WiFi',
  'WiFiClientSecure.h': 'WiFiClientSecure',
  'AsyncTCP.h':         'AsyncTCP',
  'ESPAsyncWebServer.h':'ESPAsyncWebServer',
  'HTTPClient.h':       'HTTPClient',
  'WebServer.h':        'WebServer',
  'ArduinoHttpClient.h':'ArduinoHttpClient',

  // Protocols
  'PubSubClient.h':     'PubSubClient',
  'MQTT.h':             'MQTT',
  'ArduinoMqttClient.h':'ArduinoMqttClient',
  'WebSocketsClient.h': 'WebSockets',
  'WebSocketsServer.h': 'WebSockets',

  // Storage
  'SD.h':               'SD',
  'SPIFFS.h':           'SPIFFS',
  'LittleFS.h':         'LittleFS',
  'EEPROM.h':           'EEPROM',
  'Preferences.h':      'Preferences',
  'FlashStorage.h':     'FlashStorage',

  // Display
  'Adafruit_GFX.h':         'Adafruit GFX Library',
  'Adafruit_SSD1306.h':     'Adafruit SSD1306',
  'Adafruit_ST7735.h':      'Adafruit ST7735 and ST7789 Library',
  'Adafruit_ILI9341.h':     'Adafruit ILI9341',
  'TFT_eSPI.h':             'TFT_eSPI',
  'U8g2lib.h':              'U8g2',
  'LiquidCrystal.h':        'LiquidCrystal',
  'LiquidCrystal_I2C.h':    'LiquidCrystal I2C',

  // Sensors
  'DHT.h':              'DHT sensor library',
  'DHT11.h':            'DHT11',
  'Adafruit_BME280.h':  'Adafruit BME280 Library',
  'Adafruit_BMP280.h':  'Adafruit BMP280 Library',
  'Adafruit_MPU6050.h': 'Adafruit MPU6050',
  'Adafruit_HMC5883_U.h':'Adafruit HMC5883 Unified',
  'VL53L0X.h':          'VL53L0X',
  'NewPing.h':          'NewPing',
  'OneWire.h':          'OneWire',
  'DallasTemperature.h':'DallasTemperature',

  // Communication
  'SoftwareSerial.h':   'SoftwareSerial',
  'AltSoftSerial.h':    'AltSoftSerial',
  'IRremote.h':         'IRremote',
  'RH_RF95.h':          'RadioHead',
  'LoRa.h':             'LoRa',
  'nRF24L01.h':         'RF24',
  'RF24.h':             'RF24',

  // Servos & motors
  'Servo.h':            'Servo',
  'AccelStepper.h':     'AccelStepper',
  'AFMotor.h':          'Adafruit Motor Shield library',

  // Time
  'TimeLib.h':          'Time',
  'RTClib.h':           'RTClib',
  'DS3231.h':           'DS3231',
  'NTPClient.h':        'NTPClient',

  // JSON / data
  'ArduinoJson.h':      'ArduinoJson',
  'FastLED.h':          'FastLED',
  'Adafruit_NeoPixel.h':'Adafruit NeoPixel',
};

// ── Regex patterns ──────────────────────────────────────────────────

const MISSING_HEADER_RE  = /fatal error:\s*([^:]+\.h(?:pp)?)\s*:\s*No such file or directory/i;
const INCLUDE_RE         = /#include\s*[<"]([^>"]+)[>"]/g;

// ── Analyzer ────────────────────────────────────────────────────────

/**
 * Scan compile errors + source code to find missing libraries.
 *
 * @param {import('../utils/error-parser').ParsedError[]} errors
 * @param {string} sourceCode   - full sketch source
 * @returns {MissingLibrary[]}
 */
export function detectMissingLibraries(errors, sourceCode = '') {
  const missing = new Map();  // header → MissingLibrary

  // 1. Scan structured errors for MISSING_HEADER / MISSING_LIBRARY codes
  for (const err of errors) {
    const m = MISSING_HEADER_RE.exec(err.message || '');
    if (m) {
      const header = m[1].trim();
      if (!missing.has(header)) {
        missing.set(header, makeSuggestion(header, err.file, err.line));
      }
    }
    if (err.message?.includes('No such file or directory')) {
      const h = extractHeaderFromError(err.message);
      if (h && !missing.has(h)) {
        missing.set(h, makeSuggestion(h, err.file, err.line));
      }
    }
  }

  // 2. Cross-reference all #include statements in source against known headers
  //    Any included header that's NOT in the standard SDK likely needs a library.
  if (sourceCode && missing.size === 0) {
    let m;
    INCLUDE_RE.lastIndex = 0;
    while ((m = INCLUDE_RE.exec(sourceCode)) !== null) {
      const header = m[1];
      if (isThirdPartyHeader(header) && HEADER_TO_LIBRARY[header] && !missing.has(header)) {
        missing.set(header, makeSuggestion(header, null, null));
      }
    }
  }

  return Array.from(missing.values());
}

/**
 * @typedef {Object} MissingLibrary
 * @property {string}      header      - The included header file
 * @property {string|null} library     - The installable library name, if known
 * @property {string|null} file        - Source file where it's included
 * @property {number|null} line        - Line number
 * @property {boolean}     known       - Whether we have a library mapping
 * @property {string}      installCmd  - CLI install command
 */
function makeSuggestion(header, file, line) {
  const library = HEADER_TO_LIBRARY[header] || null;
  return {
    header,
    library,
    file:       file || null,
    line:       line || null,
    known:      library != null,
    installCmd: library ? `companion lib install "${library}"` : null,
  };
}

function extractHeaderFromError(msg) {
  const m = /[<"]([^>"]+\.h(?:pp)?)[>"]/i.exec(msg);
  return m ? m[1] : null;
}

// Headers that are part of the Arduino core SDK (don't need a library)
const CORE_HEADERS = new Set([
  'Arduino.h', 'avr/io.h', 'avr/interrupt.h', 'avr/pgmspace.h',
  'avr/wdt.h', 'util/delay.h', 'inttypes.h', 'stdint.h', 'stdbool.h',
  'stddef.h', 'stdlib.h', 'string.h', 'math.h', 'stdio.h',
  'Wire.h', 'SPI.h', 'EEPROM.h', 'HardwareSerial.h', 'Print.h',
  'Stream.h', 'WString.h', 'IPAddress.h', 'Udp.h', 'Client.h',
  'Server.h', 'Printable.h', 'WCharacter.h', 'USBAPI.h',
  'pins_arduino.h', 'wiring_private.h',
  // ESP32 core headers
  'esp_system.h', 'esp_wifi.h', 'esp_event.h', 'esp_log.h',
  'nvs_flash.h', 'esp32/rom/crc.h', 'freertos/FreeRTOS.h',
  'freertos/task.h', 'driver/gpio.h',
]);

function isThirdPartyHeader(header) {
  if (CORE_HEADERS.has(header)) return false;
  // Skip relative includes (these are local files)
  if (header.startsWith('./') || header.startsWith('../')) return false;
  // Must be a .h/.hpp file
  return header.endsWith('.h') || header.endsWith('.hpp');
}

// ── Library name normalizer ─────────────────────────────────────────

/**
 * Try to guess a library name from an unknown header.
 * e.g. "MyCustomLib.h" → "MyCustomLib"
 */
export function guessLibraryName(header) {
  return header
    .replace(/\.h(pp)?$/i, '')
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .trim();
}

// ── Well-known mappings export ───────────────────────────────────────
export const KNOWN_HEADER_MAP = { ...HEADER_TO_LIBRARY };
