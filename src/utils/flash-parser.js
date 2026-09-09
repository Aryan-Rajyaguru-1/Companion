/**
 * flash-parser.js
 * Parses flash and RAM usage from arduino-cli compile output.
 *
 * arduino-cli outputs lines like:
 *   Sketch uses 14832 bytes (4%) of program storage space. Maximum is 253952 bytes.
 *   Global variables use 2172 bytes (6%) of dynamic memory, leaving 5988 bytes for local variables. Maximum is 8192 bytes.
 *
 * Returns null if output does not contain usage lines (e.g. failed compile).
 */

const FLASH_RE = /Sketch uses (\d+) bytes \((\d+)%\) of program storage space\. Maximum is (\d+) bytes/i;
const RAM_RE   = /Global variables use (\d+) bytes \((\d+)%\) of dynamic memory.*?Maximum is (\d+) bytes/i;

/**
 * @param {string} output — full compiler stdout/stderr
 * @returns {{ flash: FlashUsage, ram: RamUsage } | null}
 */
export function parseFlashUsage(output) {
  if (!output) return null;

  const flashMatch = FLASH_RE.exec(output);
  const ramMatch   = RAM_RE.exec(output);

  if (!flashMatch && !ramMatch) return null;

  const result = {};

  if (flashMatch) {
    const used    = parseInt(flashMatch[1], 10);
    const pct     = parseInt(flashMatch[2], 10);
    const maximum = parseInt(flashMatch[3], 10);
    result.flash = { used, pct, maximum, free: maximum - used };
  }

  if (ramMatch) {
    const used    = parseInt(ramMatch[1], 10);
    const pct     = parseInt(ramMatch[2], 10);
    const maximum = parseInt(ramMatch[3], 10);
    result.ram = { used, pct, maximum, free: maximum - used };
  }

  return Object.keys(result).length > 0 ? result : null;
}

// roundHalfEven implements ties-go-to-even ("banker's") rounding so values
// landing exactly on a .x5 boundary (e.g. 1.25 → "1.2") don't over-report
// usage, while ordinary fractions still round to nearest.
function roundHalfEven(x) {
  const f = Math.floor(x);
  const diff = x - f;
  if (diff > 0.5) return f + 1;
  if (diff < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

export function formatBytes(n) {
  if (n == null) return '—';
  if (n >= 1024 * 1024) return `${(roundHalfEven((n / (1024 * 1024)) * 10) / 10).toFixed(1)} MB`;
  if (n >= 1024)        return `${(roundHalfEven((n / 1024) * 10) / 10).toFixed(1)} KB`;
  return `${n} B`;
}

// Severity colour thresholds — matches Arduino IDE warning colours
export function usageSeverity(pct) {
  if (pct >= 90) return 'critical';   // red
  if (pct >= 75) return 'warning';    // yellow
  return 'ok';                        // teal/green
}
