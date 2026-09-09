/**
 * error-parser.test.js
 * Tests for the unified GCC output parser.
 * Run: npm test (requires vitest or jest in package.json)
 */

import { describe, it, expect } from 'vitest';
import {
  parseCompilerErrors,
  parseJsonDiagnostics,
  mergeErrors,
  errorsToMarkers,
  errorSummary,
  classifyLine,
} from '../error-parser';

// ── parseCompilerErrors ────────────────────────────────────────

describe('parseCompilerErrors', () => {
  it('parses full GCC format: file:line:col: severity: message', () => {
    const output = '/tmp/sketch/sketch.ino:10:5: error: expected \';\' before \'}\' token';
    const errors  = parseCompilerErrors(output);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toMatchObject({
      file:     '/tmp/sketch/sketch.ino',
      line:     10,
      col:      5,
      severity: 'error',
      message:  "expected ';' before '}' token",
    });
  });

  it('parses no-column format: file:line: severity: message', () => {
    const output = '/tmp/sketch/sketch.ino:7: warning: unused variable';
    const errors  = parseCompilerErrors(output);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toMatchObject({ line: 7, col: 1, severity: 'warning' });
  });

  it('normalises "fatal error" to "error"', () => {
    const output = '/tmp/a.ino:3:1: fatal error: DHT.h: No such file or directory';
    const errors  = parseCompilerErrors(output);
    expect(errors[0].severity).toBe('error');
  });

  it('deduplicates identical errors', () => {
    const line   = '/tmp/sketch.ino:5:3: error: x undeclared';
    const errors = parseCompilerErrors([line, line].join('\n'));
    expect(errors).toHaveLength(1);
  });

  it('ignores non-GCC lines', () => {
    const output = 'Compiling sketch...\nLinking...\n✓ Done';
    expect(parseCompilerErrors(output)).toHaveLength(0);
  });

  it('handles multiple errors across multiple files', () => {
    const output = [
      '/sketch/sketch.ino:10:3: error: foo undeclared',
      '/sketch/helpers.h:2:1: warning: #pragma once',
      '/sketch/sketch.ino:15:1: error: expected }',
    ].join('\n');
    const errors = parseCompilerErrors(output);
    expect(errors).toHaveLength(3);
    expect(errors.filter(e => e.severity === 'error')).toHaveLength(2);
  });
});

// ── parseJsonDiagnostics ──────────────────────────────────────

describe('parseJsonDiagnostics', () => {
  it('returns [] for empty input', () => {
    expect(parseJsonDiagnostics([])).toEqual([]);
    expect(parseJsonDiagnostics(null)).toEqual([]);
  });

  it('maps structured diagnostics correctly', () => {
    const diags = [
      { file: '/sketch.ino', line: 12, col: 4, severity: 'error', message: 'bad syntax' },
      { file: '/sketch.ino', line: 20, col: 1, severity: 'warning', message: 'unused var' },
    ];
    const result = parseJsonDiagnostics(diags);
    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({ line: 12, col: 4, severity: 'error' });
    expect(result[1]).toMatchObject({ severity: 'warning' });
  });

  it('filters entries without file or line', () => {
    const diags = [{ severity: 'note', message: 'no location' }];
    expect(parseJsonDiagnostics(diags)).toHaveLength(0);
  });
});

// ── mergeErrors ───────────────────────────────────────────────

describe('mergeErrors', () => {
  it('prefers JSON errors over regex errors when JSON is non-empty', () => {
    const regex = [{ file: 'a', line: 1, col: 1, severity: 'error', message: 'regex' }];
    const json  = [{ file: 'a', line: 1, col: 4, severity: 'error', message: 'json'  }];
    expect(mergeErrors(regex, json)).toBe(json);
  });

  it('falls back to regex when JSON is empty', () => {
    const regex = [{ file: 'a', line: 1, col: 1, severity: 'error', message: 'regex' }];
    expect(mergeErrors(regex, [])).toBe(regex);
  });
});

// ── errorsToMarkers ───────────────────────────────────────────

describe('errorsToMarkers', () => {
  const errors = [
    { file: '/tmp/sketch/sketch.ino', line: 5, col: 3, severity: 'error',   message: 'bad' },
    { file: '/tmp/sketch/helpers.h',  line: 2, col: 1, severity: 'warning', message: 'warn' },
  ];

  it('filters by basename match', () => {
    const markers = errorsToMarkers(errors, '/other/path/sketch.ino');
    expect(markers).toHaveLength(1);
    expect(markers[0].startLineNumber).toBe(5);
  });

  it('assigns Monaco severity codes', () => {
    const markers = errorsToMarkers(errors, '/tmp/sketch/sketch.ino');
    expect(markers[0].severity).toBe(8); // Error
  });

  it('returns empty array for unknown file', () => {
    expect(errorsToMarkers(errors, 'other.cpp')).toHaveLength(0);
  });

  it('uses wide end column for no-column errors (col=1)', () => {
    const e = [{ file: 'sketch.ino', line: 1, col: 1, severity: 'error', message: 'x' }];
    const m = errorsToMarkers(e, 'sketch.ino');
    expect(m[0].endColumn).toBe(999);
  });
});

// ── errorSummary ──────────────────────────────────────────────

describe('errorSummary', () => {
  it('counts correctly', () => {
    const errors = [
      { severity: 'error' }, { severity: 'error' },
      { severity: 'warning' }, { severity: 'note' },
    ];
    expect(errorSummary(errors)).toEqual({ errors: 2, warnings: 1, notes: 1 });
  });

  it('handles empty array', () => {
    expect(errorSummary([])).toEqual({ errors: 0, warnings: 0, notes: 0 });
  });
});

// ── classifyLine ──────────────────────────────────────────────

describe('classifyLine', () => {
  it('classifies GCC error line', () => {
    const result = classifyLine('/sketch.ino:10:5: error: missing ;');
    expect(result.type).toBe('error');
    expect(result.line).toBe(10);
    expect(result.file).toBe('/sketch.ino');
  });

  it('classifies GCC warning line', () => {
    const result = classifyLine('/sketch.ino:3:1: warning: unused variable');
    expect(result.type).toBe('warning');
  });

  it('classifies success line', () => {
    expect(classifyLine('✓ compiled successfully').type).toBe('success');
    expect(classifyLine('upload complete').type).toBe('success');
  });

  it('classifies info line', () => {
    expect(classifyLine('» Compiling sketch…').type).toBe('info');
    expect(classifyLine('Connecting to bridge…').type).toBe('info');
  });

  it('returns output type for unclassified lines', () => {
    expect(classifyLine('some random text').type).toBe('output');
    expect(classifyLine('').type).toBe('output');
  });

  it('returns null file for non-error lines', () => {
    expect(classifyLine('hello').file).toBeNull();
  });
});
