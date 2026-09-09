/**
 * flash-parser.test.js
 * Tests for flash and RAM usage parsing from arduino-cli compile output.
 */

import { describe, it, expect } from 'vitest';
import { parseFlashUsage, formatBytes, usageSeverity } from '../flash-parser';

// ── parseFlashUsage ───────────────────────────────────────────

describe('parseFlashUsage', () => {
  const FULL_OUTPUT = `
Compiling sketch...
Linking...
Sketch uses 14832 bytes (4%) of program storage space. Maximum is 253952 bytes.
Global variables use 2172 bytes (6%) of dynamic memory, leaving 5988 bytes for local variables. Maximum is 8192 bytes.
`;

  it('parses flash usage', () => {
    const result = parseFlashUsage(FULL_OUTPUT);
    expect(result?.flash).toBeDefined();
    expect(result.flash.used).toBe(14832);
    expect(result.flash.pct).toBe(4);
    expect(result.flash.maximum).toBe(253952);
    expect(result.flash.free).toBe(253952 - 14832);
  });

  it('parses RAM usage', () => {
    const result = parseFlashUsage(FULL_OUTPUT);
    expect(result?.ram).toBeDefined();
    expect(result.ram.used).toBe(2172);
    expect(result.ram.pct).toBe(6);
    expect(result.ram.maximum).toBe(8192);
  });

  it('returns null for empty/failed compile output', () => {
    expect(parseFlashUsage('')).toBeNull();
    expect(parseFlashUsage(null)).toBeNull();
    expect(parseFlashUsage('error: undefined reference to `setup\'')).toBeNull();
  });

  it('returns partial result when only flash line present', () => {
    const output = 'Sketch uses 5000 bytes (2%) of program storage space. Maximum is 253952 bytes.';
    const result  = parseFlashUsage(output);
    expect(result?.flash).toBeDefined();
    expect(result?.ram).toBeUndefined();
  });

  it('handles ESP32 output format', () => {
    const output = `
Sketch uses 254944 bytes (19%) of program storage space. Maximum is 1310720 bytes.
Global variables use 20124 bytes (6%) of dynamic memory, leaving 307556 bytes for local variables. Maximum is 327680 bytes.
`;
    const result = parseFlashUsage(output);
    expect(result.flash.pct).toBe(19);
    expect(result.flash.maximum).toBe(1310720);
    expect(result.ram.used).toBe(20124);
  });

  it('handles near-full flash (edge case)', () => {
    const output = 'Sketch uses 253952 bytes (100%) of program storage space. Maximum is 253952 bytes.';
    const result  = parseFlashUsage(output);
    expect(result.flash.pct).toBe(100);
    expect(result.flash.free).toBe(0);
  });
});

// ── formatBytes ───────────────────────────────────────────────

describe('formatBytes', () => {
  it('formats bytes under 1KB', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(0)).toBe('0 B');
  });

  it('formats KB range', () => {
    expect(formatBytes(14832)).toBe('14.5 KB');
    expect(formatBytes(1024)).toBe('1.0 KB');
  });

  it('formats MB range', () => {
    expect(formatBytes(1310720)).toBe('1.2 MB');
  });

  it('handles null/undefined', () => {
    expect(formatBytes(null)).toBe('—');
    expect(formatBytes(undefined)).toBe('—');
  });
});

// ── usageSeverity ─────────────────────────────────────────────

describe('usageSeverity', () => {
  it('returns ok below 75%',       () => { expect(usageSeverity(4)).toBe('ok'); expect(usageSeverity(74)).toBe('ok'); });
  it('returns warning 75–89%',     () => { expect(usageSeverity(75)).toBe('warning'); expect(usageSeverity(89)).toBe('warning'); });
  it('returns critical at 90%+',   () => { expect(usageSeverity(90)).toBe('critical'); expect(usageSeverity(100)).toBe('critical'); });
  it('returns ok at exactly 0%',   () => { expect(usageSeverity(0)).toBe('ok'); });
});
