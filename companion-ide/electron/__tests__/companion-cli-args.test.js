// Renderer-facing CLI arguments must not become flags. These tests inspect the
// argv the wrapper builds without spawning a process.
import { describe, it, expect } from 'vitest';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CompanionCLI = require('../companion-cli.js');

function recorder() {
  const calls = [];
  const cli = Object.create(CompanionCLI.prototype);
  cli._run = async (args) => { calls.push(args); return { stdout: '' }; };
  return { cli, calls };
}

describe('CompanionCLI argument construction', () => {
  it('terminates config get/set options before renderer values', async () => {
    const { cli, calls } = recorder();
    await cli.getConfig('directories.data');
    await cli.setConfig('directories.data', '--help');
    expect(calls[0]).toEqual(['config', 'get', '--', 'directories.data']);
    expect(calls[1]).toEqual(['config', 'set', '--', 'directories.data', '--help']);
  });

  it('rejects a config key that is not a plain key', async () => {
    const { cli, calls } = recorder();
    expect(await cli.getConfig('--config-file')).toBeNull();
    expect(await cli.setConfig('--config-file', '/etc/passwd')).toMatchObject({ success: false });
    expect(calls).toHaveLength(0);
  });

  it('rejects flag-like library names before they reach the CLI', async () => {
    const { cli, calls } = recorder();
    expect(await cli.installLibrary('-rf')).toMatchObject({ success: false });
    expect(await cli.uninstallLibrary('--help')).toMatchObject({ success: false });
    expect(calls).toHaveLength(0);

    await cli.installLibrary('ArduinoJson');
    expect(calls[0]).toEqual(['lib', 'install', '--', 'ArduinoJson']);
  });
});
