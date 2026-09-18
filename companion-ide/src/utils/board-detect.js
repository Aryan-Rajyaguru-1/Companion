/**
 * board-detect.js — decisions for automatic device verification.
 *
 * A bare USB-serial bridge (CH340, CH9102, CP210x, FT232) carries no board
 * identity: its VID/PID and product string ("USB Single Serial") are the
 * same whichever chip a vendor soldered behind it. Passive matching therefore
 * cannot name those boards, and the CLI's only remaining signal is the chip's
 * own boot-ROM banner — readable by resetting the board once.
 *
 * Because that reset restarts any running sketch, the IDE must decide
 * deliberately: verify automatically when nothing was identified, but never
 * reset the same port twice in one session, and never reset a board that
 * passive matching already named.
 */

/**
 * Choose the port to boot-ROM-probe, or null when probing is not warranted.
 *
 * @param {object}   args
 * @param {Array}    args.ports   — ports from the CLI (port, fqbn, usbVid…)
 * @param {Array}    args.matches — identified matches from `board detect`
 * @param {Set}      args.probed  — ports already probed this session
 * @returns {string|null} port path to probe
 */
export function probeCandidate({ ports = [], matches = [], probed } = {}) {
  // A named board needs no verification — and must not be reset.
  if (matches.some(m => m && m.fqbn)) return null;
  if (ports.some(p => p && p.fqbn)) return null;
  const seen = probed instanceof Set ? probed : new Set();
  const next = ports.find(p => p && p.port && !seen.has(p.port));
  return next ? next.port : null;
}

/**
 * Unwrap the `board:detect` IPC envelope.
 *
 * electron/main.js answers with { success, detection }, while the detection
 * payload itself carries { found, matches, ports }. Reading `found`/`matches`
 * straight off the envelope yields undefined for every scan, which silently
 * discarded both passive and probed results and left whatever board was
 * already selected — the reason a connected ESP32 still showed as an Uno.
 *
 * @param {object|null} res — value returned by electronAPI.detectBoard()
 * @returns {object|null} the detection payload, or null when unavailable
 */
export function unwrapDetection(res) {
  if (!res || res.success === false) return null;
  const d = res.detection;
  return d && typeof d === 'object' ? d : null;
}

/**
 * Describe a port the IDE could not identify, for the console. Kept separate
 * from the probe decision so the wording is unit-testable.
 *
 * @param {object} port — SerialPortInfo from the CLI
 * @returns {string}
 */
export function unidentifiedMessage(port = {}) {
  const id = [port.usbVid, port.usbPid].filter(Boolean).join(':');
  const label = port.productName ? ` — ${port.productName}` : '';
  const detail = id ? ` (${id}${label})` : label ? ` (${port.productName})` : '';
  return `» ${port.port} not identified${detail} — board detection needs a boot-ROM probe or a manual pick`;
}