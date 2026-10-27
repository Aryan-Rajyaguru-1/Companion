// Renderer-facing CLI arguments must not become flags. These tests inspect the
// argv the wrapper builds without spawning a process.
import { describe, it, expect } from 'vitest';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CompanionCLI = require('../companion-cli.js');

function recorder() {
  const calls = [];
  const cli = Object.create(CompanionCLI.prototype);
  cli._run = async (args, _onOutput, _onDiag, _kind, _env, input = null) => {
    calls.push({ args, input });
    return { stdout: '' };
  };
  return { cli, calls };
}

describe('CompanionCLI argument construction', () => {
  it('terminates config options before values and sends set values over stdin', async () => {
    const { cli, calls } = recorder();
    await cli.getConfig('directories.data');
    await cli.setConfig('directories.data', '--help');
    expect(calls[0]).toEqual({ args: ['config', 'get', '--', 'directories.data'], input: null });
    expect(calls[1]).toEqual({ args: ['config', 'set', '--stdin', '--', 'directories.data'], input: '--help' });
  });

  it('strips CLI color codes from config values before comparing them', async () => {
    const { cli } = recorder();
    cli._run = async () => ({
      stdout: '\u001b[38;5;37mbridge.key\u001b[0m = \u001b[36m<set>\u001b[0m\n',
    });
    await expect(cli.getConfig('bridge.key')).resolves.toBe('<set>');
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
    expect(calls[0].args).toEqual(['lib', 'install', '--', 'ArduinoJson']);
  });
});
