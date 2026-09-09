/**
 * prefs.js — Persistent preferences store
 *
 * Mirrors arduino.* preference keys from arduino-ide-main/arduino-preferences.ts
 * P1: Added schema validation (type coercion, range checks, enum validation)
 * P2: Added companion.daemon.* and companion.cache.* keys
 * P1 FQBN: companion.board.recentFQBNs tracks recently used boards
 */

// ── Schema (P1 Config + JSON Schema pattern) ──────────────────────

const SCHEMA = {
  // Upload
  'arduino.upload.autoVerify':        { type: 'boolean', default: true },
  'arduino.upload.verbose':           { type: 'boolean', default: false },
  'arduino.upload.verifyAfterUpload': { type: 'boolean', default: false },

  // Compile
  'arduino.compile.warnings':         { type: 'enum',    values: ['none','default','more','all'], default: 'default' },
  'arduino.compile.verbose':          { type: 'boolean', default: false },

  // Editor
  'arduino.editor.fontSize':          { type: 'number',  min: 8,  max: 32,    default: 14 },
  'arduino.editor.wordWrap':          { type: 'boolean', default: false },
  'arduino.editor.minimap':           { type: 'boolean', default: true },
  'arduino.editor.bracketPairs':      { type: 'boolean', default: true },

  // Serial
  'arduino.serial.baud':              { type: 'enum', values: [300,1200,2400,4800,9600,19200,38400,57600,74880,115200,230400,250000,460800,921600,2000000], default: 115200 },
  'arduino.serial.lineEnding':        { type: 'enum', values: ['','\n','\r','\r\n'], default: '\n' },
  'arduino.serial.timestamp':         { type: 'boolean', default: false },
  'arduino.serial.autoscroll':        { type: 'boolean', default: true },

  // Sketchbook
  'arduino.sketchbook.showAllFiles':  { type: 'boolean', default: false },
  'arduino.sketchbook.path':          { type: 'string',  default: '' },

  // Interface
  'arduino.window.zoomLevel':         { type: 'number',  min: -5, max: 5,     default: 0 },

  // P2 Daemon
  'companion.daemon.enabled':         { type: 'boolean', default: true },
  'companion.daemon.autoRestart':     { type: 'boolean', default: true },

  // P2 Build cache
  'companion.cache.enabled':          { type: 'boolean', default: true },
  'companion.cache.maxSizeMB':        { type: 'number',  min: 64, max: 4096,  default: 512 },
  'companion.cache.maxAgeDays':       { type: 'number',  min: 1,  max: 90,    default: 30 },

  // P1 FQBN recent boards
  'companion.board.recentFQBNs':      { type: 'json',    default: [] },

  // Templates
  'companion.templates.showOnNew':    { type: 'boolean', default: true },
};

const DEFAULTS = Object.fromEntries(Object.entries(SCHEMA).map(([k, s]) => [k, s.default]));

// ── Coerce + validate ─────────────────────────────────────────────

function coerce(key, value) {
  const s = SCHEMA[key];
  if (!s) return value;
  switch (s.type) {
    case 'boolean': return Boolean(value);
    case 'number': {
      const n = Number(value);
      if (isNaN(n)) return s.default;
      return Math.min(s.max ?? n, Math.max(s.min ?? n, n));
    }
    case 'enum': {
      if (s.values.includes(value)) return value;
      const asNum = Number(value);
      if (s.values.includes(asNum)) return asNum;
      return s.default;
    }
    case 'string': return typeof value === 'string' ? value : String(value ?? '');
    case 'json':
      if (typeof value === 'string') { try { return JSON.parse(value); } catch { return s.default; } }
      return value ?? s.default;
    default: return value;
  }
}

function validate(key, value) {
  if (!SCHEMA[key]) return { valid: false };
  const coerced = coerce(key, value);
  return { valid: true, coerced };
}

// ── Prefs class ───────────────────────────────────────────────────

class Prefs {
  constructor() { this._cache = null; }

  _load() {
    if (this._cache) return this._cache;
    try {
      const raw = localStorage.getItem('companion.prefs');
      this._cache = { ...DEFAULTS };
      if (raw) {
        for (const [k, v] of Object.entries(JSON.parse(raw))) {
          if (SCHEMA[k]) this._cache[k] = coerce(k, v);
        }
      }
    } catch { this._cache = { ...DEFAULTS }; }
    return this._cache;
  }

  _save() {
    try { localStorage.setItem('companion.prefs', JSON.stringify(this._cache)); } catch {}
  }

  get(key)         { return this._load()[key] ?? DEFAULTS[key]; }
  getAll()         { return { ...this._load() }; }
  get defaults()   { return { ...DEFAULTS }; }
  get schema()     { return SCHEMA; }

  set(key, value) {
    const { valid, coerced } = validate(key, value);
    if (!valid) return;
    this._load();
    this._cache[key] = coerced;
    this._save();
  }

  setMany(obj) {
    this._load();
    for (const [k, v] of Object.entries(obj)) {
      const { valid, coerced } = validate(k, v);
      if (valid) this._cache[k] = coerced;
    }
    this._save();
  }

  reset() { this._cache = { ...DEFAULTS }; this._save(); }

  // P1 FQBN recent board tracking
  addRecentFQBN(fqbn) {
    if (!fqbn) return;
    const list = this.get('companion.board.recentFQBNs') || [];
    this.set('companion.board.recentFQBNs', [fqbn, ...list.filter(f => f !== fqbn)].slice(0, 10));
  }

  getRecentFQBNs() { return this.get('companion.board.recentFQBNs') || []; }
}

export const prefs = new Prefs();
