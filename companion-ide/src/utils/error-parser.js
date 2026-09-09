/**
 * error-parser.js — Single source of truth for GCC output parsing.
 *
 * Structural fix: previously Console.jsx had its own classifyLine() regex,
 * and error-parser.js had another. Three independent parsers (Go errors.go,
 * JS error-parser.js, Console.jsx) all independently reimplemented GCC regex.
 *
 * Now: Console.jsx imports classifyLine() from here.
 *      error-parser.js is the canonical JS parser.
 *      Go side emits structured JSON when --json is passed (parseJsonDiagnostics).
 */

// ── Regex patterns ─────────────────────────────────────────────
const GCC_FULL_RE   = /^(.+?):(\d+):(\d+):\s+(error|warning|note|fatal error):\s+(.+)$/;
const GCC_NO_COL_RE = /^(.+?):(\d+):\s+(error|warning|note|fatal error):\s+(.+)$/;

// ── Types ──────────────────────────────────────────────────────
/**
 * @typedef {Object} ParsedError
 * @property {string} file
 * @property {number} line
 * @property {number} col
 * @property {'error'|'warning'|'note'} severity
 * @property {string} message
 */

/**
 * @typedef {Object} LineClass
 * @property {'error'|'warning'|'note'|'success'|'info'|'output'|'muted'} type
 * @property {string|null} file
 * @property {number|null} line
 * @property {number|null} col
 */

// ── Strategy 1: GCC text parsing ──────────────────────────────

/**
 * Parse raw compiler stdout/stderr into structured errors.
 * @param {string} output
 * @param {string} sketchDir
 * @returns {ParsedError[]}
 */
export function parseCompilerErrors(output, sketchDir = '') {
  const results = [];
  const lines   = output.split('\n');

  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;

    let m = GCC_FULL_RE.exec(t);
    if (m) {
      results.push({ file: normPath(m[1]), line: +m[2], col: +m[3], severity: normSev(m[4]), message: m[5].trim() });
      continue;
    }
    m = GCC_NO_COL_RE.exec(t);
    if (m) {
      results.push({ file: normPath(m[1]), line: +m[2], col: 1, severity: normSev(m[3]), message: m[4].trim() });
    }
  }
  return dedup(results);
}

// ── Strategy 2: JSON structured diagnostics ───────────────────

/**
 * Parse structured JSON diagnostics from `companion compile --json`.
 * @param {{ file, line, col, severity, message }[]} diagnostics
 * @returns {ParsedError[]}
 */
export function parseJsonDiagnostics(diagnostics) {
  if (!Array.isArray(diagnostics) || !diagnostics.length) return [];
  return diagnostics
    .filter(d => d && d.file && d.line)
    .map(d => ({
      file:     normPath(d.file),
      line:     +d.line || 1,
      col:      +d.col  || 1,
      severity: normSev(d.severity || 'error'),
      message:  String(d.message || '').trim(),
    }));
}

/** Prefer JSON (exact columns); fall back to regex */
export function mergeErrors(regexErrors, jsonErrors) {
  return jsonErrors.length > 0 ? jsonErrors : regexErrors;
}

// ── Monaco marker conversion ───────────────────────────────────

/**
 * Convert ParsedError[] → Monaco IMarkerData[] for the active file.
 */
export function errorsToMarkers(errors, filePath) {
  const activeBase = baseName(filePath);
  return errors
    .filter(e => e.file && (baseName(e.file) === activeBase || normPath(e.file) === normPath(filePath)))
    .map(e => ({
      severity:        monacoSev(e.severity),
      message:         e.message,
      startLineNumber: e.line,
      startColumn:     e.col > 0 ? e.col : 1,
      endLineNumber:   e.line,
      endColumn:       e.col > 1 ? e.col + 80 : 999,
      source:          'Companion CLI',
    }));
}

/** Returns { errors, warnings, notes } counts */
export function errorSummary(errors) {
  return {
    errors:   errors.filter(e => e.severity === 'error').length,
    warnings: errors.filter(e => e.severity === 'warning').length,
    notes:    errors.filter(e => e.severity === 'note').length,
  };
}

// ── classifyLine — exported for Console.jsx ───────────────────
// Structural fix: Console.jsx previously had its own duplicate implementation.
// Now it imports this function so there is exactly one GCC regex in JS.

/**
 * Classify a single console output line.
 * Returns a LineClass that Console uses for colour + clickability.
 * @param {string} text
 * @returns {LineClass}
 */
export function classifyLine(text) {
  if (!text) return { type: 'output', file: null, line: null, col: null };
  const t = text.trim();

  // GCC full: file:line:col: severity: message
  let m = GCC_FULL_RE.exec(t);
  if (m) {
    const sev = normSev(m[4]);
    return { type: sev, file: normPath(m[1]), line: +m[2], col: +m[3] };
  }

  // GCC no-col: file:line: severity: message
  m = GCC_NO_COL_RE.exec(t);
  if (m) {
    const sev = normSev(m[3]);
    return { type: sev, file: normPath(m[1]), line: +m[2], col: 1 };
  }

  // Semantic classification without file reference
  if (/✓|success|compiled successfully|upload complete/i.test(t)) return { type: 'success', file: null, line: null, col: null };
  if (/»|connecting|uploading|compiling|installing/i.test(t))      return { type: 'info',    file: null, line: null, col: null };

  return { type: 'output', file: null, line: null, col: null };
}

// ── Helpers ────────────────────────────────────────────────────

function normSev(s) {
  if (!s) return 'note';
  const l = s.toLowerCase();
  if (l === 'fatal error' || l === 'error') return 'error';
  if (l === 'warning') return 'warning';
  return 'note';
}

function monacoSev(s) {
  return s === 'error' ? 8 : s === 'warning' ? 4 : s === 'note' ? 2 : 1;
}

function normPath(p) { return p ? p.replace(/\\/g, '/') : ''; }
function baseName(p) { if (!p) return ''; const pts = normPath(p).split('/'); return pts[pts.length - 1]; }

function dedup(errors) {
  const seen = new Set();
  return errors.filter(e => {
    const k = `${e.file}:${e.line}:${e.col}:${e.severity}:${e.message}`;
    if (seen.has(k)) return false; seen.add(k); return true;
  });
}
