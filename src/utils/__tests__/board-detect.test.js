import { describe, it, expect } from 'vitest';
import { probeCandidate, unidentifiedMessage, unwrapDetection, deviceKey } from '../board-detect.js';

// The ESP32 DevKit V1 case: a WCH CH9102 CDC-ACM bridge whose identity is
// board-agnostic.
const devkitV1 = { port: '/dev/ttyACM0', usbVid: '1a86', usbPid: '55d4', productName: 'USB Single Serial' };

// The Seeed XIAO ESP32S3 Sense case: Espressif native USB, claimed by many
// module definitions at once.
const xiaoS3 = { port: '/dev/ttyACM0', usbVid: '303a', usbPid: '1001', serialNumber: 'CC:BA:97:00:EB:FC', productName: 'USB JTAG/serial debug unit' };

describe('automatic device verification', () => {
  it('probes an unidentified bridge port', () => {
    expect(probeCandidate({ ports: [devkitV1], matches: [], probed: new Set() })?.port).toBe('/dev/ttyACM0');
  });

  it('never resets a device that was already probed this session', () => {
    const probed = new Set([deviceKey(devkitV1)]);
    expect(probeCandidate({ ports: [devkitV1], matches: [], probed })).toBeNull();
  });

  it('re-verifies after a board swap on the same port path', () => {
    // The DevKit was verified; the XIAO now occupies the same /dev/ttyACM0.
    const probed = new Set([deviceKey(devkitV1)]);
    expect(probeCandidate({ ports: [xiaoS3], matches: [], probed })?.port).toBe('/dev/ttyACM0');
  });

  it('never resets a board that passive matching already named', () => {
    const uno = { port: '/dev/ttyACM0', usbVid: '2341', usbPid: '0043', fqbn: 'arduino:avr:uno' };
    expect(probeCandidate({ ports: [uno], matches: [{ fqbn: 'arduino:avr:uno' }], confidence: 'high', probed: new Set() })).toBeNull();
    expect(probeCandidate({ ports: [uno], matches: [{ fqbn: 'arduino:avr:uno' }], confidence: 'medium', probed: new Set() })).toBeNull();
  });

  it('verifies a fuzzy low-confidence guess instead of trusting it', () => {
    // Regression: a XIAO ESP32S3 Sense came back as the esp32 core's hidden
    // "ESP32 Family Device" placeholder via fuzzy containment, and the guess
    // suppressed the probe that would have read the real chip.
    const guess = { port: '/dev/ttyACM0', usbVid: '303a', usbPid: '1001', fqbn: 'esp32:esp32:esp32_family' };
    const cand = probeCandidate({
      ports: [guess], matches: [{ fqbn: 'esp32:esp32:esp32_family' }], confidence: 'low', probed: new Set(),
    });
    expect(cand?.port).toBe('/dev/ttyACM0');
  });

  it('handles an empty scan without throwing', () => {
    expect(probeCandidate()).toBeNull();
    expect(probeCandidate({ ports: [], matches: [] })).toBeNull();
  });

  it('unwraps the {success, detection} IPC envelope', () => {
    const payload = { found: true, fqbn: 'esp32:esp32:esp32', matches: [{ fqbn: 'esp32:esp32:esp32' }] };
    expect(unwrapDetection({ success: true, detection: payload })).toBe(payload);
  });

  it('does not confuse the envelope itself for the detection payload', () => {
    // Regression: reading .found/.matches off the envelope silently discarded
    // every detection and left a stale board selected.
    const envelope = { success: true, detection: { found: true, matches: [{ fqbn: 'esp32:esp32:esp32' }] } };
    expect(envelope.found).toBeUndefined();
    expect(envelope.matches).toBeUndefined();
    expect(unwrapDetection(envelope).found).toBe(true);
  });

  it('returns null when detection failed or is missing', () => {
    expect(unwrapDetection({ success: false, detection: null })).toBeNull();
    expect(unwrapDetection({ success: true })).toBeNull();
    expect(unwrapDetection(null)).toBeNull();
    expect(unwrapDetection(undefined)).toBeNull();
  });


  it('describes an unidentified device instead of implying a board', () => {
    const msg = unidentifiedMessage(devkitV1);
    expect(msg).toContain('/dev/ttyACM0');
    expect(msg).toContain('1a86:55d4');
    expect(msg).toContain('USB Single Serial');
    expect(msg).toMatch(/not identified/);
    // It must not invent a board name.
    expect(msg.toLowerCase()).not.toContain('uno');
  });
});