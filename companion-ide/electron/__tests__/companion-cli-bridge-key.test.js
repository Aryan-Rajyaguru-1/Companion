// The renderer must never receive the bridge key. The main process reads it
// from the CLI only at the moment it opens a LAN connection, and the CLI's
// --reveal path is the one deliberate disclosure. These tests pin the parsing
// (including ANSI stripping) and the env override that CI and power users use.
import { describe, it, expect, vi, afterEach } from 'vitest';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CompanionCLI = require('../companion-cli.js');

const makeCLI = () => Object.create(CompanionCLI.prototype);

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('CompanionCLI.getBridgeKey', () => {
  it('returns a trimmed COMPANION_BRIDGE_KEY without spawning the CLI', async () => {
    vi.stubEnv('COMPANION_BRIDGE_KEY', '  env-bridge-key  ');
    const cli = makeCLI();
    cli._run = vi.fn();

    await expect(cli.getBridgeKey()).resolves.toBe('env-bridge-key');
    expect(cli._run).not.toHaveBeenCalled();
  });

  it('reads the explicit reveal path and strips ANSI colors', async () => {
    vi.stubEnv('COMPANION_BRIDGE_KEY', '');
    const cli = makeCLI();
    cli._run = vi.fn(async () => ({
      stdout: '\u001b[38;5;37mbridge.key\u001b[0m = \u001b[36mabc12345\u001b[0m\n',
    }));

    await expect(cli.getBridgeKey()).resolves.toBe('abc12345');
    expect(cli._run).toHaveBeenCalledWith(['config', 'get', '--reveal', '--', 'bridge.key']);
  });

  it('treats <unset> as an empty key', async () => {
    vi.stubEnv('COMPANION_BRIDGE_KEY', '');
    const cli = makeCLI();
    cli._run = vi.fn(async () => ({ stdout: 'bridge.key = <unset>\n' }));

    await expect(cli.getBridgeKey()).resolves.toBe('');
  });

  it('fails closed when the CLI cannot be run', async () => {
    vi.stubEnv('COMPANION_BRIDGE_KEY', '');
    const cli = makeCLI();
    cli._run = vi.fn(async () => { throw new Error('CLI missing'); });

    await expect(cli.getBridgeKey()).rejects.toThrow(/Could not read bridge\.key/);
  });

  it('fails closed when the CLI does not reveal the key', async () => {
    vi.stubEnv('COMPANION_BRIDGE_KEY', '');
    const cli = makeCLI();
    cli._run = vi.fn(async () => ({ stdout: 'bridge.key = <set>\n' }));

    await expect(cli.getBridgeKey()).rejects.toThrow(/did not reveal bridge\.key/);
  });

  it('fails closed on an empty CLI response', async () => {
    vi.stubEnv('COMPANION_BRIDGE_KEY', '');
    const cli = makeCLI();
    cli._run = vi.fn(async () => ({ stdout: '' }));

    await expect(cli.getBridgeKey()).rejects.toThrow(/empty bridge\.key/);
  });

  it('parses a raw secret even if a future CLI omits the key label', async () => {
    vi.stubEnv('COMPANION_BRIDGE_KEY', '');
    const cli = makeCLI();
    cli._run = vi.fn(async () => ({ stdout: 'raw-secret-value\n' }));

    await expect(cli.getBridgeKey()).resolves.toBe('raw-secret-value');
  });
});
