/**
 * fqbn.js — JavaScript FQBN utilities
 * Mirrors companion-cli/internal/fqbn/fqbn.go for use in the renderer.
 *
 * P1 FQBN Standardization: All board references in the IDE use the canonical
 * vendor:architecture:board[:option=value,...] format internally.
 */

// ── Parser ──────────────────────────────────────────────────────────

/**
 * Parse a raw FQBN string into its components.
 * @param {string} raw
 * @returns {{ vendor, architecture, board, options: Record<string,string> } | null}
 */
export function parseFQBN(raw) {
  if (!raw || typeof raw !== 'string') return null;

  const parts = raw.split(':');
  if (parts.length < 3) return null;

  const vendor       = parts[0].trim();
  const architecture = parts[1].trim();
  const board        = parts[2].trim();
  const options      = {};

  if (!vendor || !architecture || !board) return null;

  // Parse menu options from 4th segment: key=value,key=value
  if (parts.length >= 4 && parts[3]) {
    for (const kv of parts[3].split(',')) {
      const idx = kv.indexOf('=');
      if (idx > 0) {
        options[kv.slice(0, idx).trim()] = kv.slice(idx + 1).trim();
      }
    }
  }

  return { vendor, architecture, board, options };
}

/**
 * Serialize parsed FQBN back to canonical string.
 * Options are sorted alphabetically.
 */
export function serializeFQBN({ vendor, architecture, board, options = {} }) {
  const core = `${vendor}:${architecture}:${board}`;
  const keys = Object.keys(options).sort();
  if (keys.length === 0) return core;
  const optStr = keys.map(k => `${k}=${options[k]}`).join(',');
  return `${core}:${optStr}`;
}

/** Validate FQBN format */
export function isValidFQBN(raw) {
  return parseFQBN(raw) !== null;
}

/** Normalize (parse + re-serialize) an FQBN string */
export function normalizeFQBN(raw) {
  const parsed = parseFQBN(raw);
  return parsed ? serializeFQBN(parsed) : raw;
}

/** Return vendor:architecture from FQBN */
export function platformID(raw) {
  const p = parseFQBN(raw);
  return p ? `${p.vendor}:${p.architecture}` : null;
}

// ── Well-known board names ──────────────────────────────────────────

const BOARD_NAMES = {
  'arduino:avr:uno':                         'Arduino Uno',
  'arduino:avr:mega':                        'Arduino Mega 2560',
  'arduino:avr:nano':                        'Arduino Nano',
  'arduino:avr:leonardo':                    'Arduino Leonardo',
  'arduino:avr:pro':                         'Arduino Pro Mini',
  'arduino:avr:micro':                       'Arduino Micro',
  'arduino:avr:yun':                         'Arduino Yún',
  'esp32:esp32:esp32':                       'ESP32 Dev Module',
  'esp32:esp32:esp32s3':                     'ESP32-S3 Dev',
  'esp32:esp32:esp32s2':                     'ESP32-S2 Dev',
  'esp32:esp32:esp32c3':                     'ESP32-C3 Dev',
  'esp32:esp32:esp32c6':                     'ESP32-C6 Dev',
  'esp32:esp32:esp32h2':                     'ESP32-H2 Dev',
  'esp8266:esp8266:nodemcuv2':               'NodeMCU 1.0 (ESP-12E)',
  'esp8266:esp8266:d1_mini':                 'Wemos D1 Mini',
  'esp8266:esp8266:nodemcu':                 'NodeMCU 0.9 (ESP-12)',
  'STMicroelectronics:stm32:Nucleo_64':      'STM32 Nucleo-64',
  'STMicroelectronics:stm32:GenF1':          'STM32 Generic F1 (BluePill)',
  'STMicroelectronics:stm32:GenF4':          'STM32 Generic F4 (BlackPill)',
  'arduino:samd:arduino_zero_edbg':          'Arduino Zero',
  'arduino:samd:mkr1000':                    'Arduino MKR1000',
  'arduino:megaavr:uno2018':                 'Arduino Uno WiFi Rev 2',
  'arduino:mbed_giga:giga':                  'Arduino GIGA R1 WiFi',
};

/**
 * Return a friendly display name for a board FQBN.
 * Falls back to the board component of the FQBN.
 */
export function friendlyName(raw) {
  const p = parseFQBN(raw);
  if (!p) return '';   // null/empty input degrades to '' (documented contract)
  const core = `${p.vendor}:${p.architecture}:${p.board}`;
  const name = BOARD_NAMES[core];
  if (name) {
    return Object.keys(p.options).length > 0 ? `${name} (custom)` : name;
  }
  return p.board;
}

/**
 * Return a short label suitable for toolbar display.
 */
export function shortLabel(raw) {
  return friendlyName(raw);
}

// ── MCU family detection ────────────────────────────────────────────

const MCU_MAP = {
  'arduino:avr':      'avr',
  'esp32:esp32':      'esp32',
  'esp8266:esp8266':  'esp8266',
  'STMicroelectronics:stm32': 'stm32',
  'arduino:samd':     'samd',
  'arduino:megaavr':  'megaavr',
  'arduino:mbed':     'mbed',
  'arduino:mbed_giga':'mbed',
  'arduino:mbed_nano':'mbed',
};

/**
 * Infer the MCU family from a FQBN.
 * Used to set the upload protocol and memory constraints display.
 */
export function mcuFromFQBN(raw) {
  const p = parseFQBN(raw);
  if (!p) return 'generic';
  return MCU_MAP[`${p.vendor}:${p.architecture}`] || 'generic';
}

// ── FQBN groups (for BoardDropdown) ────────────────────────────────

export const BOARD_GROUPS = [
  { group: 'Arduino AVR', items: [
    { label: 'Arduino Uno',        fqbn: 'arduino:avr:uno',        mcu: 'avr'   },
    { label: 'Arduino Mega 2560',  fqbn: 'arduino:avr:mega',       mcu: 'avr'   },
    { label: 'Arduino Nano',       fqbn: 'arduino:avr:nano',       mcu: 'avr'   },
    { label: 'Arduino Leonardo',   fqbn: 'arduino:avr:leonardo',   mcu: 'avr'   },
    { label: 'Arduino Pro Mini',   fqbn: 'arduino:avr:pro',        mcu: 'avr'   },
    { label: 'Arduino Micro',      fqbn: 'arduino:avr:micro',      mcu: 'avr'   },
  ]},
  { group: 'ESP32', items: [
    { label: 'ESP32 Dev Module',   fqbn: 'esp32:esp32:esp32',      mcu: 'esp32' },
    { label: 'ESP32-S3 Dev',       fqbn: 'esp32:esp32:esp32s3',    mcu: 'esp32' },
    { label: 'ESP32-S2 Dev',       fqbn: 'esp32:esp32:esp32s2',    mcu: 'esp32' },
    { label: 'ESP32-C3 Dev',       fqbn: 'esp32:esp32:esp32c3',    mcu: 'esp32' },
    { label: 'ESP32-C6 Dev',       fqbn: 'esp32:esp32:esp32c6',    mcu: 'esp32' },
  ]},
  { group: 'ESP8266', items: [
    { label: 'NodeMCU 1.0',        fqbn: 'esp8266:esp8266:nodemcuv2', mcu: 'esp8266' },
    { label: 'Wemos D1 Mini',      fqbn: 'esp8266:esp8266:d1_mini',   mcu: 'esp8266' },
  ]},
  { group: 'STM32', items: [
    { label: 'Nucleo F103RB',      fqbn: 'STMicroelectronics:stm32:Nucleo_64', mcu: 'stm32' },
    { label: 'BluePill (F103C8)',  fqbn: 'STMicroelectronics:stm32:GenF1',     mcu: 'stm32' },
    { label: 'BlackPill (F411CE)', fqbn: 'STMicroelectronics:stm32:GenF4',     mcu: 'stm32' },
  ]},
  { group: 'Arduino ARM', items: [
    { label: 'Arduino Zero',       fqbn: 'arduino:samd:arduino_zero_edbg', mcu: 'samd' },
    { label: 'Arduino MKR1000',    fqbn: 'arduino:samd:mkr1000',           mcu: 'samd' },
    { label: 'Arduino GIGA R1',    fqbn: 'arduino:mbed_giga:giga',         mcu: 'mbed' },
  ]},
];

// Flat list for search
export const ALL_BOARDS = BOARD_GROUPS.flatMap(g =>
  g.items.map(b => ({ ...b, group: g.group }))
);
