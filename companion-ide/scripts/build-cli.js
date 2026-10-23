#!/usr/bin/env node
/**
 * Build the companion CLI for packaging.
 *
 * The released IDE needs a working CLI next to its resources: without it every
 * compile, board scan and upload fails at runtime with "binary not found".
 * electron-builder copies this directory via package.json#extraResources.
 *
 * Cross-compilation is deliberately not attempted here: electron-builder
 * builds one target at a time and this script builds for the host Go target.
 */
'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ideDir = path.resolve(__dirname, '..');
const cliDir = path.resolve(ideDir, '..', 'companion-cli');
const outDir = path.join(ideDir, 'resources');
const exe = process.platform === 'win32' ? '.exe' : '';
const out = path.join(outDir, `companion${exe}`);
// The release workflow exports the tag as VERSION. Stamp it into the CLI we
// embed, otherwise the IDE's bundled `companion version` reports the Go
// default (1.0.0) while the installer and release both say the tag.
const version = process.env.VERSION && process.env.VERSION !== 'dev' ? process.env.VERSION : '';
const ldflags = version
  ? `-s -w -X github.com/companion-ide/companion-cli/cmd.CLIVersion=${version}`
  : '-s -w';

if (!fs.existsSync(path.join(cliDir, 'go.mod'))) {
  console.error(`build-cli: cannot find companion-cli/go.mod at ${cliDir}`);
  process.exit(1);
}

fs.mkdirSync(outDir, { recursive: true });

const result = spawnSync('go', ['build', '-trimpath', '-ldflags', ldflags, '-o', out, '.'], {
  cwd: cliDir,
  stdio: 'inherit',
  env: { ...process.env, CGO_ENABLED: process.env.CGO_ENABLED || '0' },
});

if (result.error) {
  console.error(`build-cli: failed to run go: ${result.error.message}`);
  process.exit(1);
}
if (result.status !== 0) {
  console.error(`build-cli: go build exited with code ${result.status}`);
  process.exit(result.status || 1);
}
if (!fs.existsSync(out) || fs.statSync(out).size === 0) {
  console.error(`build-cli: go build did not produce ${out}`);
  process.exit(1);
}

if (process.platform !== 'win32') fs.chmodSync(out, 0o755);

// Prove the stamp took inside the artifact. `go build -X` silently no-ops
// when its target stops being a var, which is exactly how releases shipped
// "1.0.0" before. Only verify when a release version was requested.
if (version) {
  const check = spawnSync(out, ['--no-color', 'version'], { encoding: 'utf8' });
  const printed = `${check.stdout || ''}${check.stderr || ''}`;
  if (check.status !== 0 || !printed.includes(version)) {
    console.error(`build-cli: embedded CLI did not report ${version}:\n${printed}`);
    process.exit(1);
  }
  console.log(`build-cli: embedded CLI reports ${version}`);
}
console.log(`build-cli: wrote ${out}`);
