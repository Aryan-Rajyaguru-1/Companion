// The bridge key is a shared secret. Main reads it from the CLI only when it
// opens a LAN connection; the renderer only writes it and displays set/unset.
// These text-level assertions guard the wiring that functional bridge tests
// cannot see (IPC boundaries), in the same spirit as ipc-wiring.test.js.
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const read = (p) => readFileSync(join(here, '..', p), 'utf8');

const mainSrc = read('main.js');
const cliSrc = read('companion-cli.js');
const preloadSrc = read('preload.js');
const settingsSrc = read('../src/components/BridgeSettings.jsx');

describe('bridge key IPC wiring', () => {
  it('main fetches the key for every LAN connection path', () => {
    // The helper is the only place that touches the secret. Every connection
    // path goes through it: upload-binary, legacy compile+upload,
    // connect-serial, and query.
    const fetches = mainSrc.match(/readBridgeKey\(\)/g) || [];
    expect(fetches.length).toBeGreaterThanOrEqual(4);
    expect(mainSrc.match(/companionCLI\.getBridgeKey\(\)/g) || []).toHaveLength(1);
  });

  it('aborts a connection when the key cannot be read', () => {
    expect(mainSrc).toContain('async function readBridgeKey()');
    const guards = mainSrc.match(/if \(error\) return \{ success: false, error \}/g) || [];
    expect(guards.length).toBeGreaterThanOrEqual(4);
  });

  it('passes the key to both upload entry points', () => {
    const uploads = mainSrc.match(/bridgeClient\.uploadFirmware\(\{[^}]*bridgeKey[^}]*\}\)/gs) || [];
    expect(uploads.length).toBe(2);
  });

  it('passes the key to serial connect and status query', () => {
    expect(mainSrc).toMatch(/\},\s*bridgeKey\);/);
    expect(mainSrc).toMatch(/bridgeClient\.query\([^)]*bridgeKey\)/);
  });

  it('main reads the explicit reveal path and strips ANSI', () => {
    expect(cliSrc).toContain("'config', 'get', '--reveal'");
    expect(cliSrc).toContain('replace(/\\x1b\\[[0-9;]*m/g');
  });

  it('preload exposes no key getter to the renderer', () => {
    expect(preloadSrc).not.toMatch(/getBridgeKey|bridgeKey/);
  });

  it('settings read only set/unset and never fetch the secret', () => {
    expect(settingsSrc).toContain("companionConfigGet?.('bridge.key')");
    expect(settingsSrc).toContain("companionConfigSet?.('bridge.key'");
    expect(settingsSrc).not.toContain('getBridgeKey');
    // The status display must not interpolate a value returned by the getter.
    expect(settingsSrc).not.toMatch(/setKeyStatus\(value\)/);
  });

});
