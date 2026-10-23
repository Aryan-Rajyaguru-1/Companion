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

if (!fs.existsSync(path.join(cliDir, 'go.mod'))) {
  console.error(`build-cli: cannot find companion-cli/go.mod at ${cliDir}`);
  process.exit(1);
}

fs.mkdirSync(outDir, { recursive: true });

const result = spawnSync('go', ['build', '-trimpath', '-o', out, '.'], {
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
console.log(`build-cli: wrote ${out}`);
