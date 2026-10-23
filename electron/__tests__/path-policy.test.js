// Tests for the shipped renderer path policy. The policy lives in
// electron/path-policy.js so main.js and this suite cannot drift apart.
import { describe, it, expect } from 'vitest';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { createPathPolicy } from '../path-policy.js';

const deny = createPathPolicy();

describe('renderer path policy', () => {
  it('permits the OS temp dir even when it lives under /var (macOS shape)', () => {
    const macTmp = '/var/folders/ab/xyz/T';
    const policy = createPathPolicy({ tmpDir: macTmp });
    expect(policy.isDenied(macTmp)).toBe(false);
    expect(policy.isDenied(macTmp + '/companion_sketch123/sketch.ino')).toBe(false);
  });

  it('still denies sensitive parts of /var and /private/var', () => {
    expect(deny.isDenied('/var/db/something')).toBe(true);
    expect(deny.isDenied('/var/log/x')).toBe(true);
    // macOS resolves /var through /private/var. A realpath-based policy must
    // deny both spellings, not just the one the user typed.
    expect(deny.isDenied('/private/var/db/anything')).toBe(true);
    expect(deny.isDenied('/private/var/log/anything')).toBe(true);
    // /var/folders itself is deliberately allowed: on macOS it is the
    // per-user sandbox container that tmpdir lives inside.
    expect(deny.isDenied('/var/folders/ab/xyz/T/sketch.ino')).toBe(false);
  });

  it('denies mixed-case system directories after normalisation', () => {
    // These entries used to never match because norm was lowercased but the
    // denylist was not.
    expect(deny.isDenied('/System/Library/CoreServices')).toBe(true);
    expect(deny.isDenied('/Library/Preferences/com.apple.foo.plist')).toBe(true);
  });

  it('denies a symlink that points into a denied directory', () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pol-'));
    const link = path.join(tmp, 'innocent');
    fs.symlinkSync('/etc', link);
    expect(deny.isDenied(link)).toBe(true);
    // The path does not exist yet, but its nearest existing ancestor is the
    // symlink; resolving only the full path would have missed this.
    expect(deny.isDenied(path.join(link, 'new-file'))).toBe(true);
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  it('rejects parent traversal before resolving symlinks', () => {
    if (process.platform === 'win32') return; // symlink creation needs elevation
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pol-dotdot-'));
    const link = path.join(tmp, 'innocent');
    fs.symlinkSync('/', link);
    // The OS resolves "innocent" to "/" before applying "..", so this names
    // /etc/passwd. path.resolve() alone would call it <tmp>/etc/passwd.
    expect(deny.isDenied(`${link}/../etc/passwd`)).toBe(true);
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  it('denies a broken symlink whose target is in a denied directory', () => {
    if (process.platform === 'win32') return; // symlink creation needs elevation
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pol-broken-'));
    const link = path.join(tmp, 'innocent');
    const target = path.join(os.homedir(), '.ssh', 'authorized_keys');
    fs.symlinkSync(target, link);
    expect(deny.isDenied(link)).toBe(true);
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  it('denies shell profiles and autostart locations, not just ~/.ssh', () => {
    const home = os.homedir();
    for (const p of ['.ssh/id_ed25519', '.bashrc', '.zshrc', '.profile',
                     'Library/LaunchAgents/evil.plist',
                     'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/evil.exe',
                     '.local/share/systemd/user/evil.service']) {
      expect(deny.isDenied(path.join(home, p)), `${p} should be denied`).toBe(true);
    }
  });

  it('denies secrets even inside the permitted temp directory', () => {
    const tmp = os.tmpdir();
    expect(deny.isDenied(path.join(tmp, '.env'))).toBe(true);
    expect(deny.isDenied(path.join(tmp, 'nested', 'auth-token'))).toBe(true);
    expect(deny.isDenied(path.join(tmp, 'server.pem'))).toBe(true);
  });

  it('still allows an ordinary sketch folder', () => {
    expect(deny.isDenied(path.join(os.homedir(), 'Documents', 'Sketches'))).toBe(false);
    expect(deny.isDenied(path.join(os.tmpdir(), 'companion_sketchABC', 'blink.ino'))).toBe(false);
  });
});
