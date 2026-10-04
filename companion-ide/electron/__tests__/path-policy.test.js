// Mirrors the path sandbox in electron/main.js registerIPC. Kept as a copy
// rather than an import because the policy is a closure inside registerIPC,
// which needs a live Electron app; duplicating the constants here means a
// change to main.js has to be mirrored deliberately, and these assertions
// document why each entry exists.
import { describe, it, expect } from 'vitest';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';

const DENY_DIRS = [
  '/etc', '/usr', '/bin', '/sbin', '/lib', '/lib64', '/boot',
  '/proc', '/sys', '/dev', '/root', '/opt/homebrew', '/System', '/Library',
  // '/var' is deliberately absent: on macOS os.tmpdir() is /var/folders/...,
  // so denying /var broke every temp-sketch compile — and also broke the
  // fallback at the os:mkdtemp handler, since that fallback IS os.tmpdir().
  '/var/db', '/var/root', '/var/log', '/var/run', '/var/vm', '/private/etc',
];
const DENY_HOME_SUFFIXES = [
  '.ssh', '.aws', '.gnupg', '.kube', '.docker', '.config', '.gnome2',
  'keyrings', '.companion-cli', '.companion-relay', '.arduino15',
  'Library/LaunchAgents', 'Library/LaunchDaemons',
  'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup',
  '.bashrc', '.bash_profile', '.profile', '.zshrc', '.zprofile', '.zshenv',
];
const DENY_NAME_RE = /(^|[\\/])(auth-token|\.env(\..*)?|.*\.(pem|key|p12|pfx))$/i;

const realpath = (p) => {
  try { return fs.realpathSync.native ? fs.realpathSync.native(p) : fs.realpathSync(p); }
  catch { return null; }
};

function makeIsDenied(fakeTmp) {
  return (p) => {
    if (!p) return true;
    let norm = path.resolve(p).replace(/\\/g, '/').toLowerCase();
    const resolved = realpath(p);
    if (resolved) norm = resolved.replace(/\\/g, '/').toLowerCase();

    const tmp = (fakeTmp || os.tmpdir() || '').replace(/\\/g, '/').toLowerCase();
    if (tmp && (norm === tmp || norm.startsWith(tmp + '/'))) return false;

    for (const d of DENY_DIRS) if (norm === d || norm.startsWith(d + '/')) return true;
    const home = (os.homedir() || '').replace(/\\/g, '/').toLowerCase();
    if (home) for (const s of DENY_HOME_SUFFIXES) {
      const suf = s.toLowerCase();
      if (norm === `${home}/${suf}` || norm.startsWith(`${home}/${suf}/`)) return true;
    }
    return DENY_NAME_RE.test(norm);
  };
}

describe('renderer path policy', () => {
  it('permits the OS temp dir even when it lives under /var (macOS shape)', () => {
    const macTmp = '/var/folders/ab/xyz/T/companion_sketch123';
    expect(makeIsDenied(macTmp)(macTmp)).toBe(false);
    expect(makeIsDenied(macTmp)(macTmp + '/sketch.ino')).toBe(false);
  });

  it('still denies the sensitive parts of /var', () => {
    const d = makeIsDenied();
    expect(d('/var/db/something')).toBe(true);
    expect(d('/var/log/x')).toBe(true);
    // /var/folders itself is deliberately allowed: on macOS it is the
    // per-user sandbox container that tmpdir lives inside, so denying it is
    // what broke the IDE's temp-sketch compile.
  });

  it('denies a symlink that points into a denied directory', () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pol-'));
    const link = path.join(tmp, 'innocent');
    fs.symlinkSync('/etc', link);
    expect(makeIsDenied()(link)).toBe(true);
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  it('denies shell profiles and autostart locations, not just ~/.ssh', () => {
    const d = makeIsDenied();
    const home = os.homedir();
    for (const p of ['.bashrc', '.zshrc', '.profile',
                     'Library/LaunchAgents/evil.plist',
                     'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/evil.exe']) {
      expect(d(path.join(home, p)), `${p} should be denied`).toBe(true);
    }
  });

  it('still allows an ordinary sketch folder', () => {
    expect(makeIsDenied()(path.join(os.homedir(), 'Documents', 'Sketches'))).toBe(false);
  });
});
