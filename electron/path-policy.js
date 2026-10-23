// Path policy for renderer-supplied filesystem operations.
//
// Extracted from electron/main.js so the tests exercise the shipped policy
// instead of a copy that can drift. It is a denylist, not an allowlist: the
// sketch flow can legitimately reach directories the user never picked in a
// dialog (recent folders, argv, CLI setup output), while the realistic damage
// is system directories and credential stores.

const fs = require('fs');
const os = require('os');
const path = require('path');

const POSIX_DENY_DIRS = [
  '/etc', '/usr', '/bin', '/sbin', '/lib', '/lib64', '/boot',
  '/proc', '/sys', '/dev', '/root', '/run', '/opt/homebrew', '/System', '/Library',
  '/var/db', '/var/lib', '/var/log', '/var/root', '/var/run', '/var/spool', '/var/vm',
  // macOS resolves /etc and /var through /private, so realpath() produces
  // /private/... for these. Both spellings must be denied.
  '/private/etc', '/private/var/db', '/private/var/lib', '/private/var/log',
  '/private/var/root', '/private/var/run', '/private/var/spool', '/private/var/vm',
];

const DENY_HOME_SUFFIXES = [
  '.ssh', '.aws', '.gnupg', '.kube', '.docker', '.config', '.gnome2',
  'keyrings', '.companion-cli', '.companion-relay', '.arduino15',
  '.netrc', '.npmrc', '.password-store', '.git-credentials',
  '.mozilla', '.thunderbird', '.claude', '.codex', '.cursor',
  // Persistence locations: a compromised renderer that can write a shell
  // profile, a launch agent or a Startup-folder entry gets code execution on
  // the next login.
  'Library/LaunchAgents', 'Library/LaunchDaemons',
  'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup',
  'AppData/Roaming/Microsoft/Credentials', 'AppData/Local/Microsoft/Credentials',
  'AppData/Roaming/Microsoft/Protect', 'AppData/Local/Microsoft/Protect',
  '.local/bin', '.local/share/autostart', '.local/share/systemd', '.local/share/keyrings',
  '.bashrc', '.bash_profile', '.profile', '.zshrc', '.zprofile', '.zshenv',
];

// `auth-token` anywhere is the daemon credential; .env and key material are
// secrets regardless of which permitted directory contains them.
const DENY_NAME_RE = /(^|[\\/])(auth-token|\.env(\..*)?|.*\.(pem|key|p12|pfx))$/i;

function normalize(p) {
  if (!p) return '';
  return path.resolve(String(p)).replace(/\\/g, '/').toLowerCase();
}

// `..` must be rejected before path.resolve() collapses it: the OS resolves
// symlinks before applying "..", so /tmp/link/../etc/passwd can mean /etc/passwd
// even though path.resolve() would turn it into /tmp/etc/passwd. A resolved
// path has no ".." left, so this check must see the caller's original string.
function hasParentTraversal(p) {
  return String(p).split(/[\\/]+/).some(part => part === '..');
}

function platformDenyDirs() {
  if (process.platform !== 'win32') return [];
  const dirs = [];
  for (const key of ['SystemRoot', 'windir', 'ProgramFiles', 'ProgramFiles(x86)', 'ProgramData']) {
    if (process.env[key]) dirs.push(process.env[key]);
  }
  dirs.push('C:\\Windows', 'C:\\Program Files', 'C:\\Program Files (x86)');
  return dirs;
}

const DENY_DIRS = Array.from(new Set(
  [...POSIX_DENY_DIRS, ...platformDenyDirs()].map(normalize).filter(Boolean)
));

function realpath(p) {
  try {
    return fs.realpathSync.native ? fs.realpathSync.native(p) : fs.realpathSync(p);
  } catch {
    return null; // does not exist yet (e.g. a path about to be created)
  }
}

function createPathPolicy({ tmpDir = os.tmpdir(), homeDir = os.homedir(), realpathFn = realpath } = {}) {
  // For a path that does not exist yet, resolve its nearest existing ancestor
  // and append the remaining segments. Checking only the full path let
  // /tmp/allowed-link/new-file bypass the policy when allowed-link points at
  // /etc and new-file had not been created yet.
  //
  // realpath() fails on a *broken* symlink, so also follow the link target
  // manually. Otherwise a link in an allowed directory whose target does not
  // exist yet (say ~/.ssh/authorized_keys) would be treated as a new ordinary
  // file and written through.
  const resolveForPolicy = (p) => {
    let cur = path.resolve(p);
    const tail = [];
    const seen = new Set();
    for (;;) {
      const resolved = realpathFn(cur);
      if (resolved) {
        return tail.length ? path.join(resolved, ...tail.reverse()) : resolved;
      }
      let target = null;
      try {
        target = fs.readlinkSync(cur);
      } catch {
        // Not a symlink (or not readable); keep walking up.
      }
      if (target !== null) {
        if (seen.has(cur)) return null; // symlink loop
        // A broken/unresolvable link is followed by hand. Reject a target that
        // contains "..": resolving it lexically would lose the order in which
        // the OS follows any nested links.
        if (hasParentTraversal(target)) return null;
        seen.add(cur);
        cur = path.resolve(path.dirname(cur), target);
        continue;
      }
      const parent = path.dirname(cur);
      if (parent === cur) return null;
      tail.push(path.basename(cur));
      cur = parent;
    }
  };

  const tmp = normalize(realpathFn(tmpDir) || tmpDir);
  const home = normalize(realpathFn(homeDir) || homeDir);

  const isDenied = (p) => {
    if (!p) return true;
    if (hasParentTraversal(p)) return true;
    const resolved = resolveForPolicy(p);
    if (!resolved) return true; // unresolved (e.g. a symlink loop) is not permitted
    const norm = normalize(resolved);

    for (const d of DENY_DIRS) {
      if (norm === d || norm.startsWith(d + '/')) return true;
    }
    if (home) {
      for (const s of DENY_HOME_SUFFIXES) {
        const suffix = s.toLowerCase();
        if (norm === `${home}/${suffix}` || norm.startsWith(`${home}/${suffix}/`)) return true;
      }
    }
    if (DENY_NAME_RE.test(norm)) return true;

    // The OS temp directory is permitted last, not first: temp should not
    // become a loophole for /tmp/.env, /tmp/auth-token or a symlink into a
    // denied directory (which resolves before this check).
    if (tmp && (norm === tmp || norm.startsWith(tmp + '/'))) return false;
    return false;
  };

  return { isDenied, resolveForPolicy };
}

module.exports = {
  createPathPolicy,
  normalize,
  DENY_DIRS,
  DENY_HOME_SUFFIXES,
  DENY_NAME_RE,
};
