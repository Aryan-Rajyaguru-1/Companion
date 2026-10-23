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
 * Stable identity for a port's *device* (not its path).
 *
 * A board swap keeps the same /dev/ttyACM0 (or COMx) path, so a guard keyed on
 * the path would refuse to re-verify the new board. VID/PID plus the chip's
 * USB serial number survives the path being reused.
 *
 * @param {object} port — SerialPortInfo from the CLI
 * @returns {string}
 */
export function deviceKey(port = {}) {
  const id = [port.usbVid, port.usbPid, port.serialNumber].filter(Boolean).join(':');
  return id || port.port || '';
}

/**
 * Choose the port to boot-ROM-probe, or null when probing is not warranted.
 *
 * A "low" confidence match is a containment guess from the CLI's fuzzy
 * matcher — it names a real board but has no evidence behind it (a XIAO
 * ESP32S3 Sense once came back as "ESP32 Family Device" that way). Verify
 * rather than trust it.
 *
 * @param {object}   args
 * @param {Array}    args.ports      — ports from the CLI
 * @param {Array}    args.matches    — identified matches from `board detect`
 * @param {string}   args.confidence — detection confidence ("high"|"medium"|"low")
 * @param {Set}      args.probed     — deviceKeys already probed this session
 * @returns {object|null} the port to probe
 */
export function probeCandidate({ ports = [], matches = [], confidence, probed } = {}) {
  const seen = probed instanceof Set ? probed : new Set();
  const identified = matches.find(m => m && m.fqbn);
  // Evidence-backed matches are left alone — and must not be reset.
  if (identified && confidence !== 'low') return null;
  const next = ports.find(p => p && p.port && !seen.has(deviceKey(p)));
  return next || null;
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