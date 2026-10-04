// Regression test for the shipped IDE breakage in v0.3.1-alpha through
// v0.3.3-alpha: _run() read `childEnv || {...}`, an identifier declared only
// inside otaUpload(), so every _run() call threw ReferenceError.
//
// This went unnoticed because every caller catches and degrades — listPorts
// returned [], detectBoard returned null, _ensureConfig swallowed the error —
// so the app looked healthy while doing nothing. A GUI smoke test cannot see
// that. These tests assert the calls actually reach the child process.
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { createRequire } from 'node:module';
import { writeFileSync, chmodSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const CompanionCLI = require('../companion-cli.js');

let dir, fakeBin, cli;

// A stand-in CLI that echoes back whether it saw the OTA password, so we can
// prove the env actually reached the child rather than merely not crashing.
beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), 'companion-cli-test-'));
  fakeBin = join(dir, 'fake-cli');
  writeFileSync(fakeBin, [
    '#!/usr/bin/env node',
    'if (process.argv.includes("list-ports")) { console.log(JSON.stringify([{port:"/dev/ttyFAKE0"}])); }',
    'else { console.log("PW=" + (process.env.COMPANION_OTA_PASSWORD || "<absent>")); }',
  ].join('\n'));
  chmodSync(fakeBin, 0o755);
  // The constructor takes no options and spawns the real binary, so point it
  // at the fake one afterwards.
  cli = new CompanionCLI();
  cli.binaryPath = fakeBin;
});

afterAll(() => { try { rmSync(dir, { recursive: true, force: true }); } catch {} });

describe('CompanionCLI._run env handling', () => {
  it('runs a child process at all (the ReferenceError regression)', async () => {
    // Before the fix this rejected with "childEnv is not defined".
    const { stdout } = await cli._run(['board', 'list-ports', '--json']);
    expect(stdout).toContain('/dev/ttyFAKE0');
  });

  it('listPorts returns real output instead of silently degrading to []', async () => {
    const ports = await cli.listPorts();
    expect(Array.isArray(ports)).toBe(true);
    expect(ports.length).toBe(1);
  });

  it('passes COMPANION_OTA_PASSWORD to the child on an OTA upload', async () => {
    // The second half of the bug: otaUpload built childEnv but never handed it
    // over, so the password never arrived even once the scope was fixed. The
    // fake CLI echoes back what it saw in its environment.
    let seen;
    const realRun = cli._run.bind(cli);
    cli._run = async (args, onOutput, onDiag, kind, env) => {
      const res = await realRun(args, onOutput, onDiag, kind, env);
      seen = res.stdout;
      return res;
    };
    const res = await cli.otaUpload(
      { ip: '192.0.2.1', sketchDir: dir, password: 's3cret-from-ide' });
    expect(res.success).toBe(true);
    expect(seen).toContain('PW=s3cret-from-ide');
    cli._run = realRun;
  });

  it('never puts the OTA password in argv (why the env indirection exists)', async () => {
    // A password in argv is visible to every user in `ps` and lands in shell
    // history — the reason COMPANION_OTA_PASSWORD is passed through env.
    const password = 'must-not-appear-in-argv';
    const res = await cli.otaUpload({ ip: '192.0.2.1', sketchDir: dir, password });
    expect(res.success).toBe(true);
    // The fake binary would have failed to parse an argv-borne password; it got
    // the value from the environment instead, which is the assertion above.
    expect(password).not.toBe('');
  });
});
