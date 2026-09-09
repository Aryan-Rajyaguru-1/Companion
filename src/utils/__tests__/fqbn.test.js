/**
 * fqbn.test.js
 * Tests for the FQBN parser utilities.
 */

import { describe, it, expect } from 'vitest';
import {
  parseFQBN, serializeFQBN, isValidFQBN, normalizeFQBN,
  platformID, friendlyName, mcuFromFQBN,
} from '../fqbn';

// ── parseFQBN ─────────────────────────────────────────────────

describe('parseFQBN', () => {
  it('parses basic 3-segment FQBN', () => {
    const result = parseFQBN('arduino:avr:uno');
    expect(result).toMatchObject({ vendor: 'arduino', architecture: 'avr', board: 'uno', options: {} });
  });

  it('parses FQBN with menu options', () => {
    const result = parseFQBN('arduino:avr:mega:cpu=atmega2560');
    expect(result.options).toEqual({ cpu: 'atmega2560' });
  });

  it('parses FQBN with multiple menu options', () => {
    const result = parseFQBN('esp32:esp32:esp32:freq=240,psram=enabled');
    expect(result.options).toEqual({ freq: '240', psram: 'enabled' });
  });

  it('returns null for empty string', () => {
    expect(parseFQBN('')).toBeNull();
    expect(parseFQBN(null)).toBeNull();
  });

  it('returns null for incomplete FQBN (< 3 segments)', () => {
    expect(parseFQBN('arduino:avr')).toBeNull();
    expect(parseFQBN('arduino')).toBeNull();
  });

  it('handles STMicro long vendor name', () => {
    const result = parseFQBN('STMicroelectronics:stm32:Nucleo_64');
    expect(result.vendor).toBe('STMicroelectronics');
    expect(result.board).toBe('Nucleo_64');
  });
});

// ── serializeFQBN ─────────────────────────────────────────────

describe('serializeFQBN', () => {
  it('serializes basic FQBN', () => {
    expect(serializeFQBN({ vendor: 'arduino', architecture: 'avr', board: 'uno', options: {} }))
      .toBe('arduino:avr:uno');
  });

  it('serializes with options — sorted alphabetically', () => {
    const result = serializeFQBN({
      vendor: 'esp32', architecture: 'esp32', board: 'esp32',
      options: { psram: 'enabled', freq: '240' },
    });
    expect(result).toBe('esp32:esp32:esp32:freq=240,psram=enabled');
  });
});

// ── normalizeFQBN ─────────────────────────────────────────────

describe('normalizeFQBN', () => {
  it('normalizes FQBN with unsorted options', () => {
    const result = normalizeFQBN('esp32:esp32:esp32:psram=enabled,freq=240');
    expect(result).toBe('esp32:esp32:esp32:freq=240,psram=enabled');
  });

  it('passes through valid FQBN unchanged (no options)', () => {
    expect(normalizeFQBN('arduino:avr:uno')).toBe('arduino:avr:uno');
  });

  it('returns original string for invalid FQBN', () => {
    expect(normalizeFQBN('not-an-fqbn')).toBe('not-an-fqbn');
  });
});

// ── isValidFQBN ───────────────────────────────────────────────

describe('isValidFQBN', () => {
  it('validates correct FQBNs',    () => { expect(isValidFQBN('arduino:avr:uno')).toBe(true); expect(isValidFQBN('esp32:esp32:esp32s3')).toBe(true); });
  it('rejects incomplete FQBNs',   () => { expect(isValidFQBN('arduino:avr')).toBe(false); });
  it('rejects empty string',       () => { expect(isValidFQBN('')).toBe(false); expect(isValidFQBN(null)).toBe(false); });
});

// ── platformID ────────────────────────────────────────────────

describe('platformID', () => {
  it('extracts vendor:architecture', () => {
    expect(platformID('arduino:avr:uno')).toBe('arduino:avr');
    expect(platformID('esp32:esp32:esp32:freq=240')).toBe('esp32:esp32');
  });
  it('returns null for invalid', () => { expect(platformID('bad')).toBeNull(); });
});

// ── friendlyName ──────────────────────────────────────────────

describe('friendlyName', () => {
  it('returns known board names',    () => { expect(friendlyName('arduino:avr:uno')).toBe('Arduino Uno'); expect(friendlyName('esp32:esp32:esp32')).toBe('ESP32 Dev Module'); });
  it('returns board segment for unknown', () => { expect(friendlyName('custom:hw:myboard')).toBe('myboard'); });
  it('appends (custom) for boards with options', () => { expect(friendlyName('arduino:avr:mega:cpu=atmega2560')).toContain('custom'); });
  it('handles null/empty gracefully', () => { expect(friendlyName('')).toBe(''); expect(friendlyName(null)).toBe(''); });
});

// ── mcuFromFQBN ───────────────────────────────────────────────

describe('mcuFromFQBN', () => {
  it('maps arduino:avr → avr',        () => { expect(mcuFromFQBN('arduino:avr:uno')).toBe('avr');    });
  it('maps esp32:esp32 → esp32',      () => { expect(mcuFromFQBN('esp32:esp32:esp32')).toBe('esp32'); });
  it('maps esp8266:esp8266 → esp8266',() => { expect(mcuFromFQBN('esp8266:esp8266:nodemcuv2')).toBe('esp8266'); });
  it('maps stm32 → stm32',            () => { expect(mcuFromFQBN('STMicroelectronics:stm32:Nucleo_64')).toBe('stm32'); });
  it('returns generic for unknown',   () => { expect(mcuFromFQBN('custom:hw:board')).toBe('generic'); });
});
