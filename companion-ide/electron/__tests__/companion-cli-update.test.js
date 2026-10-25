// The CLI owns release lookup and checksum verification. These tests assert
// that the IDE wrapper invokes it with the expected arguments and only switches
// to the managed binary after a successful install.
import { describe, it, expect } from 'vitest';
import { createRequire } from 'node:module';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const CompanionCLI = require('../companion-cli.js');

function recorder(result) {
  const calls = [];
  const cli = Object.create(CompanionCLI.prototype);
  const dir = mkdtempSync(join(tmpdir(), 'companion-ide-update-'));
  cli.managedBinaryPath = join(dir, 'bin', 'companion');
  cli.binaryPath = '/packaged/companion';
  cli._daemon = {
    running: false,
    isDaemonRunning() { return this.running; },
    stop() { this.stopped = true; },
  };
  cli.stopped = false;
  cli.started = 0;
  cli.stopDaemonAndWait = async function () {
    this.stopped = true;
    this._daemon.running = false;
    return true;
  };
  cli.startDaemon = async function () { this.started++; this._daemon.running = true; return { success: true }; };
  cli._run = async (args) => {
    calls.push(args);
    if (result instanceof Error) throw result;
    return { stdout: typeof result === 'string' ? result : JSON.stringify(result) };
  };
  return { cli, calls, dir };
}

describe('CompanionCLI update commands', () => {
  it('checks with the stable --check --json contract', async () => {
    const { cli, calls, dir } = recorder({
      current_version: '0.3.4-alpha',
      latest_version: '0.3.5-alpha',
      update_available: true,
      assets: [{ name: 'Companion.IDE-0.3.5-alpha.AppImage', url: 'https://example.test/a' }],
    });
    const result = await cli.checkForUpdate();
    expect(calls[0]).toEqual(['self-update', '--check', '--json']);
    expect(result).toMatchObject({
      success: true,
      current_version: '0.3.4-alpha',
      latest_version: '0.3.5-alpha',
      update_available: true,
    });
    rmSync(dir, { recursive: true, force: true });
  });

  it('tolerates a diagnostic line before the JSON object', async () => {
    const { cli, dir } = recorder('warning: cache unavailable\n{"current_version":"1.0.0","latest_version":"1.1.0"}\n');
    const result = await cli.checkForUpdate();
    expect(result.success).toBe(true);
    expect(result.latest_version).toBe('1.1.0');
    rmSync(dir, { recursive: true, force: true });
  });

  it('surfaces a failed check without changing the binary', async () => {
    const { cli, dir } = recorder(new Error('release lookup failed'));
    const result = await cli.checkForUpdate();
    expect(result).toEqual({ success: false, error: 'release lookup failed' });
    expect(cli.binaryPath).toBe('/packaged/companion');
    rmSync(dir, { recursive: true, force: true });
  });

  it('installs to the writable managed path and switches to it', async () => {
    const { cli, calls, dir } = recorder({
      updated: true,
      install_path: '',
      current_version: '0.3.4-alpha',
      latest_version: '0.3.5-alpha',
      checksum_verified: true,
    });
    cli._run = async (args) => {
      calls.push(args);
      return { stdout: JSON.stringify({
        updated: true,
        install_path: cli.managedBinaryPath,
        current_version: '0.3.4-alpha',
        latest_version: '0.3.5-alpha',
        checksum_verified: true,
      }) };
    };

    const result = await cli.applyUpdate();
    expect(calls[0]).toEqual(['self-update', '--json', '--target', cli.managedBinaryPath]);
    expect(result.success).toBe(true);
    expect(result.updated).toBe(true);
    expect(cli.binaryPath).toBe(cli.managedBinaryPath);
    // A new daemon manager must point at the updated binary.
    expect(cli._daemon._binary).toBe(cli.managedBinaryPath);
    rmSync(dir, { recursive: true, force: true });
  });

  it('stops and restarts a running daemon around the update', async () => {
    const { cli, dir } = recorder({
      updated: true,
      install_path: '',
    });
    const target = cli.managedBinaryPath;
    cli._daemon.running = true;
    cli._run = async () => ({ stdout: JSON.stringify({
      updated: true, install_path: target, checksum_verified: true,
    }) });

    const result = await cli.applyUpdate();
    expect(cli.stopped).toBe(true);
    expect(cli.started).toBe(1);
    expect(result.success).toBe(true);
    rmSync(dir, { recursive: true, force: true });
  });

  it('does not switch binaries when the release is already current', async () => {
    const { cli, dir } = recorder({ updated: false, checksum_verified: false });
    const result = await cli.applyUpdate();
    expect(result.success).toBe(true);
    expect(result.updated).toBe(false);
    expect(cli.binaryPath).toBe('/packaged/companion');
    rmSync(dir, { recursive: true, force: true });
  });

  it('reports a failed install and leaves the old binary path in place', async () => {
    const { cli, dir } = recorder(new Error('checksum mismatch'));
    const result = await cli.applyUpdate();
    expect(result.success).toBe(false);
    expect(result.error).toContain('checksum');
    expect(cli.binaryPath).toBe('/packaged/companion');
    rmSync(dir, { recursive: true, force: true });
  });
});
