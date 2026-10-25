/**
 * update-policy.js
 *
 * Pure release-selection policy for the IDE updater. This module deliberately
 * has no Electron or filesystem dependencies so its version ordering and
 * installer selection can be tested directly.
 *
 * The CLI publishes the release metadata (including every asset) in
 * `self-update --check --json`. The IDE compares its own app.getVersion()
 * against the same release tag and picks an installer only when the published
 * asset actually matches the host platform and architecture. Not every release
 * has an installer for every target; callers must degrade to the release page
 * when `installer` is null instead of opening a wrong-architecture download.
 */

const PLATFORM_NAMES = {
  linux: 'linux',
  win32: 'windows',
  windows: 'windows',
  darwin: 'macos',
  macos: 'macos',
};

const ARCH_NAMES = {
  x64: 'x64',
  x86_64: 'x64',
  amd64: 'x64',
  arm64: 'arm64',
  aarch64: 'arm64',
  ia32: 'x86',
  i386: 'x86',
};

function normalizePlatform(platform) {
  return PLATFORM_NAMES[String(platform || '').toLowerCase()] || '';
}

function normalizeArch(arch) {
  return ARCH_NAMES[String(arch || '').toLowerCase()] || '';
}

function normalizeVersion(value) {
  return String(value || '').trim().replace(/^[vV]/, '').split('+')[0];
}

function parseVersion(value) {
  const text = normalizeVersion(value);
  const match = text.match(/^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?$/);
  if (!match) return null;
  return {
    numbers: [Number(match[1]), Number(match[2] || 0), Number(match[3] || 0)],
    prerelease: match[4] ? match[4].split('.') : [],
  };
}

function comparePrereleaseIdentifiers(a, b) {
  const aNumeric = /^\d+$/.test(a);
  const bNumeric = /^\d+$/.test(b);
  if (aNumeric && bNumeric) {
    const ai = Number(a);
    const bi = Number(b);
    return ai === bi ? 0 : ai < bi ? -1 : 1;
  }
  // Numeric identifiers have lower precedence than alphanumeric identifiers.
  if (aNumeric !== bNumeric) return aNumeric ? -1 : 1;
  return a === b ? 0 : a < b ? -1 : 1;
}

function compareVersions(a, b) {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  if (!pa && !pb) return 0;
  if (!pa) return -1;
  if (!pb) return 1;

  for (let i = 0; i < 3; i++) {
    if (pa.numbers[i] !== pb.numbers[i]) {
      return pa.numbers[i] < pb.numbers[i] ? -1 : 1;
    }
  }

  // A final release is newer than any prerelease of the same core version.
  if (pa.prerelease.length === 0 && pb.prerelease.length === 0) return 0;
  if (pa.prerelease.length === 0) return 1;
  if (pb.prerelease.length === 0) return -1;

  const count = Math.max(pa.prerelease.length, pb.prerelease.length);
  for (let i = 0; i < count; i++) {
    if (pa.prerelease[i] === undefined) return -1;
    if (pb.prerelease[i] === undefined) return 1;
    const cmp = comparePrereleaseIdentifiers(pa.prerelease[i], pb.prerelease[i]);
    if (cmp !== 0) return cmp;
  }
  return 0;
}

function isNewer(latest, current) {
  if (!parseVersion(latest)) return false;
  if (!parseVersion(current)) return true;
  return compareVersions(latest, current) > 0;
}

function assetArchitecture(name) {
  const text = String(name || '').toLowerCase();
  if (text.includes('universal')) return 'universal';
  if (text.includes('arm64') || text.includes('aarch64')) return 'arm64';
  if (text.includes('x86_64') || text.includes('x64') || text.includes('amd64')) return 'x64';
  if (text.includes('ia32') || text.includes('i386')) return 'x86';
  return '';
}

function architectureMatches(assetArch, wantedArch) {
  if (!wantedArch) return false;
  if (assetArch === 'universal') return true;
  if (!assetArch) {
    // Current release jobs build these un-suffixed assets on x64 runners. An
    // un-suffixed AppImage/NSIS installer therefore must not be offered to an
    // arm64 host, where it will not run.
    return wantedArch === 'x64';
  }
  return assetArch === wantedArch;
}

function installerKind(platform, name) {
  const lower = String(name || '').toLowerCase();
  if (platform === 'linux' && lower.endsWith('.appimage')) return 'linux-appimage';
  if (platform === 'linux' && lower.endsWith('.deb')) return 'linux-deb';
  if (platform === 'windows' && lower.endsWith('.exe')) return 'windows-installer';
  if (platform === 'macos' && lower.endsWith('.dmg')) return 'macos-dmg';
  return '';
}

function isIdeInstallerName(platform, name) {
  const lower = String(name || '').toLowerCase();
  if (platform === 'linux') {
    return /^companion\.ide-.*\.appimage$/i.test(name) || /^companion-ide_.*\.deb$/i.test(name);
  }
  if (platform === 'windows') {
    return /^companion\.ide\.setup\..+\.exe$/i.test(name);
  }
  if (platform === 'macos') {
    return /^companion\.ide-.*\.dmg$/i.test(name);
  }
  return false;
}

/**
 * Pick the best IDE installer for the host. Returns null when this release did
 * not publish a compatible artifact; the UI then opens the release page.
 */
function selectIdeInstaller(assets, platform, arch) {
  const platformName = normalizePlatform(platform);
  const wantedArch = normalizeArch(arch);
  if (!platformName || !wantedArch || !Array.isArray(assets)) return null;

  const candidates = [];
  for (const asset of assets) {
    if (!asset || typeof asset !== 'object') continue;
    const name = String(asset.name || '');
    const url = String(asset.url || asset.browser_download_url || '');
    if (!name || !url || !isIdeInstallerName(platformName, name)) continue;
    if (!architectureMatches(assetArchitecture(name), wantedArch)) continue;
    const kind = installerKind(platformName, name);
    if (!kind) continue;
    const priority = kind === 'linux-appimage' ? 0 : kind === 'linux-deb' ? 1 : 0;
    candidates.push({ name, url, kind, priority, size: Number(asset.size) || undefined });
  }

  if (candidates.length === 0) return null;
  candidates.sort((a, b) => a.priority - b.priority || a.name.localeCompare(b.name));
  const best = candidates[0];
  return { name: best.name, url: best.url, kind: best.kind, size: best.size };
}

/**
 * Only allow links that point at this project's GitHub release pages/downloads
 * over HTTPS. Release metadata crosses a network boundary; an unexpected URL
 * must never be handed to shell.openExternal().
 */
function isTrustedReleaseUrl(rawUrl, repo = 'Aryan-Rajyaguru-1/Companion', kind = '') {
  try {
    const url = new URL(String(rawUrl || ''));
    if (url.protocol !== 'https:') return false;
    if (!['github.com', 'www.github.com'].includes(url.hostname.toLowerCase())) return false;
    if (url.username || url.password) return false;
    const prefix = `/${String(repo)}/releases/`;
    if (!url.pathname.startsWith(prefix)) return false;
    if (kind === 'download') return url.pathname.startsWith(`${prefix}download/`);
    if (kind === 'tag') return url.pathname.startsWith(`${prefix}tag/`);
    return true;
  } catch {
    return false;
  }
}

/**
 * Build the normalized IDE half of the update status consumed by the renderer.
 * `release` is the CLI's CheckResult JSON (snake_case on the wire).
 */
function buildIdeUpdate(release, currentVersion, platform, arch) {
  const latestVersion = normalizeVersion(release?.latest_version || release?.tag_name || '');
  const current = String(currentVersion || '');
  const installer = selectIdeInstaller(release?.assets || [], platform, arch);
  return {
    currentVersion: current,
    latestVersion,
    updateAvailable: !!latestVersion && isNewer(latestVersion, current),
    releaseName: String(release?.release_name || release?.tag_name || ''),
    releaseUrl: String(release?.release_url || release?.html_url || ''),
    publishedAt: String(release?.published_at || ''),
    prerelease: !!release?.prerelease,
    releaseNotes: String(release?.release_notes || ''),
    installer: installer || null,
  };
}

module.exports = {
  normalizeVersion,
  compareVersions,
  isNewer,
  assetArchitecture,
  selectIdeInstaller,
  isTrustedReleaseUrl,
  buildIdeUpdate,
};
