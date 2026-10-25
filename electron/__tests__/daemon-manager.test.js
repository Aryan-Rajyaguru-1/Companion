// The daemon used to hand its bearer token to the IDE on stdout, which the IDE
// copied into the console pane and logs. These tests run the real manager
// against a stand-in daemon and assert the private-token-file handshake:
// success, missing file, and cleanup of the 0700 directory.
import { describe, it, expect, afterEach } from 'vitest';
import { createRequire } from 'node:module';
import { writeFileSync, chmodSync, mkdtempSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const DaemonManager = require('../services/daemon-manager.js');

let managers = [];

async function waitFor(predicate, timeoutMs = 2_000) {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error('timed out waiting for condition');
    await new Promise(resolve => setTimeout(resolve, 25));
  }
}

function fakeDaemon(body) {
  const dir = mkdtempSync(join(tmpdir(), 'fake-daemon-'));
  const bin = join(dir, 'fake-daemon');
  writeFileSync(bin, '#!/bin/sh\n' + body, { mode: 0o700 });
  chmodSync(bin, 0o700);
  return bin;
}

afterEach(() => {
  for (const m of managers) {
    try { m.stop(); } catch {}
  }
  managers = [];
});

describe('DaemonManager token-file handshake', () => {
  it('reads the token from the private file and removes it on stop', async () => {
    const bin = fakeDaemon([
      'if [ -z "$COMPANION_DAEMON_TOKEN_FILE" ]; then exit 2; fi',
      'umask 077',
      'printf %s test-token > "$COMPANION_DAEMON_TOKEN_FILE"',
      'echo "COMPANION_DAEMON_PORT=45678"',
      'trap "exit 0" TERM INT',
      'while true; do sleep 1; done',
      '',
    ].join('\n'));
    const m = new DaemonManager(bin);
    managers.push(m);

    const port = await m.start();
    expect(port).toBe(45678);
    expect(m._token).toBe('test-token');
    expect(existsSync(m._tokenFile)).toBe(true);
    const tokenFile = m._tokenFile;
    const tokenDir = m._tokenDir;

    m.stop();
    expect(existsSync(tokenFile)).toBe(false);
    expect(existsSync(tokenDir)).toBe(false);
  });

  it('refuses readiness when the daemon prints a port but writes no token', async () => {
    const bin = fakeDaemon([
      'echo "COMPANION_DAEMON_PORT=45679"',
      'sleep 5',
      '',
    ].join('\n'));
    const m = new DaemonManager(bin);
    managers.push(m);

    await expect(m.start()).rejects.toThrow(/did not write|token/i);
    expect(m.isDaemonRunning()).toBe(false);
  });

  it('makes every concurrent start() caller wait for readiness', async () => {
    const bin = fakeDaemon([
      'umask 077',
      'printf %s test-token > "$COMPANION_DAEMON_TOKEN_FILE"',
      'echo "COMPANION_DAEMON_PORT=45680"',
      'trap "exit 0" TERM INT',
      'while true; do sleep 1; done',
      '',
    ].join('\n'));
    const m = new DaemonManager(bin);
    managers.push(m);

    const [p1, p2] = await Promise.all([m.start(), m.start()]);
    expect(p1).toBe(45680);
    expect(p2).toBe(45680);
    expect(m.isDaemonRunning()).toBe(true);
    expect(m._token).toBe('test-token');
  });

  it('stopAndWait waits for the child process to exit', async () => {
    const bin = fakeDaemon([
      'umask 077',
      'printf %s test-token > "$COMPANION_DAEMON_TOKEN_FILE"',
      'echo "COMPANION_DAEMON_PORT=45682"',
      'trap "exit 0" TERM INT',
      'while true; do sleep 1; done',
      '',
    ].join('\n'));
    const m = new DaemonManager(bin);
    managers.push(m);

    await m.start();
    const proc = m._proc;
    expect(await m.stopAndWait(2_000)).toBe(true);
    expect(m.isDaemonRunning()).toBe(false);
    expect(proc.exitCode !== null || proc.signalCode !== null).toBe(true);
  });

  it('clears the token and private directory when the daemon exits after startup', async () => {
    const bin = fakeDaemon([
      'umask 077',
      'printf %s test-token > "$COMPANION_DAEMON_TOKEN_FILE"',
      'echo "COMPANION_DAEMON_PORT=45681"',
      'sleep 0.2',
      '',
    ].join('\n'));
    const m = new DaemonManager(bin);
    managers.push(m);

    expect(await m.start()).toBe(45681);
    const tokenDir = m._tokenDir;
    const tokenFile = m._tokenFile;
    await waitFor(() => !m.isDaemonRunning());
    expect(m._token).toBe(null);
    expect(existsSync(tokenDir)).toBe(false);
    expect(existsSync(tokenFile)).toBe(false);
  });
});
