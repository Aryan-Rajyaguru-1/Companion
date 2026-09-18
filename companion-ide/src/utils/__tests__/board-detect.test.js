import { describe, it, expect } from 'vitest';
import { probeCandidate, unidentifiedMessage } from '../board-detect.js';

// The ESP32 DevKit V1 case, as reported by the CLI: a WCH CH9102 CDC-ACM
// bridge whose identity is board-agnostic.
const devkitV1 = { port: '/dev/ttyACM0', usbVid: '1a86', usbPid: '55d4', productName: 'USB Single Serial' };

describe('automatic device verification', () => {
  it('probes an unidentified bridge port', () => {
    expect(probeCandidate({ ports: [devkitV1], matches: [], probed: new Set() })).toBe('/dev/ttyACM0');
  });

  it('never resets a port that was already probed this session', () => {
    const probed = new Set(['/dev/ttyACM0']);
    expect(probeCandidate({ ports: [devkitV1], matches: [], probed })).toBeNull();
  });

  it('never resets a board that passive matching already named', () => {
    const uno = { port: '/dev/ttyACM0', usbVid: '2341', usbPid: '0043', fqbn: 'arduino:avr:uno' };
    expect(probeCandidate({ ports: [uno], matches: [{ fqbn: 'arduino:avr:uno' }], probed: new Set() })).toBeNull();
    // A stale match array must not cause a reset of a named port either.
    expect(probeCandidate({ ports: [uno], matches: [], probed: new Set() })).toBeNull();
  });

  it('handles an empty scan without throwing', () => {
    expect(probeCandidate()).toBeNull();
    expect(probeCandidate({ ports: [], matches: [] })).toBeNull();
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